## Отчет по лабораторной работе №1 - Docker
### Вариант 2: Разработка утилиты для запуска контейнеров

---

### 1. Цель работы

Разработать утилиту на языке Python, которая запускает команду в изолированном контейнере с использованием namespaces и overlayfs.

### Требования к утилите

1. Конфигурация через файл `config.json`
2. Создание PID, Mount, UTS namespaces
3. Установка hostname из конфига
4. Создание директории `/var/lib/mycontainer/{id}`
5. Использование Alpine Linux в качестве rootfs
6. Настройка overlayfs (lowerdir, upperdir, workdir, merged)
7. Запуск команды как PID 1 в foreground режиме
8. Монтирование /proc внутри контейнера
---

### 2. Подготовка окружения

Для начала создадим директорию утилиты и хранилище контейнеров

- `~/mycontainer` - директория для исходного кода утилиты
- `/var/lib/mycontainer` - баз хранилище данных контейнеров (аналог `/var/lib/docker`)
- `/var/lib/mycontainer/rootfs` - базовая файловая система для всех контейнеров

Это соответствует требованию задания о создании директории `/var/lib/{имя-утилиты}/{id}`.

---

### 3. Загрузка базового образа Alpine Linux дял исп в качестве rootfs

```bash
cd /var/lib/mycontainer
sudo wget https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/x86_64/alpine-minirootfs-3.19.1-x86_64.tar.gz
sudo tar -xzf alpine-minirootfs-3.19.1-x86_64.tar.gz -C rootfs
sudo rm alpine-minirootfs-3.19.1-x86_64.tar.gz 
```

- Скачали мин образ Alpine Linux 
- Распаковали в директорию `/var/lib/mycontainer/rootfs` удалили после распаковки архив ненужный
- Это будет использоваться как lowerdir в overlayfs

<img width="698" height="140" alt="image" src="https://github.com/user-attachments/assets/d78d010c-1198-40da-bb71-639be9296835" />

---

### 4.  Создадим минимальный конфиг с параметром hostname

По заданию утилита должна конфигурироваться через `config.json` по спецификации OCI

**Содержимое config.json:**
```json
{
    "hostname": "mycontainer"
}
```

---

### 5. Разработка утилиты

**Код утилиты `mycontainer.py` :**
```python
#!/usr/bin/env python3
import os, sys, json, subprocess, argparse
from pathlib import Path

def load_config(config_path):
    with open(config_path) as f:
        return json.load(f)

def setup_container_dirs(container_id):
    base_path = Path(f"/var/lib/mycontainer/{container_id}")
    base_path.mkdir(parents=True, exist_ok=True)
    (base_path / "upper").mkdir(exist_ok=True)
    (base_path / "work").mkdir(exist_ok=True)
    (base_path / "merged").mkdir(exist_ok=True)
    return base_path

def mount_overlayfs(container_id, base_path):
    rootfs_base = "/var/lib/mycontainer/rootfs"
    merged_path = base_path / "merged"
    options = f"lowerdir={rootfs_base},upperdir={base_path}/upper,workdir={base_path}/work"
    subprocess.run(["mount", "-t", "overlay", "overlay", "-o", options, str(merged_path)], check=True)
    return merged_path

def run_container(container_id, command, hostname):
    base_path = setup_container_dirs(container_id)
    merged_path = mount_overlayfs(container_id, base_path)
    
    print(f"[+] Контейнер {container_id} запущен")
    print(f"[+] Команда: {' '.join(command)}")
    
    init_script = f"""#!/bin/sh
mount -t proc proc /proc
hostname {hostname}
exec {" ".join(command)}
"""
    script_path = merged_path / "init.sh"
    with open(script_path, 'w') as f:
        f.write(init_script)
    os.chmod(script_path, 0o755)
    
    container_cmd = ["unshare", "--fork", "--pid", "--mount", "--uts", "chroot", str(merged_path), "/init.sh"]
    process = subprocess.Popen(container_cmd)
    process.wait()
    
    subprocess.run(["umount", str(merged_path)], check=False)
    return process.returncode

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', '-c', required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('cmd', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    
    if os.geteuid() != 0:
        print("[-] Требуются права root")
        sys.exit(1)
    
    config = load_config(args.config)
    hostname = config.get('hostname', 'container')
    exit_code = run_container(args.id, args.cmd, hostname)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
```

**Что реализовано в коде:**

1. **`setup_container_dirs()`** - создает директорию `/var/lib/mycontainer/{id}` с поддиректориями upper, work, merged. Это соотв требованию о создании директории для каж контейнера

2. **`mount_overlayfs()`** - монтирует overlayfs:
   - lowerdir: базовый Alpine rootfs
   - upperdir: `/var/lib/mycontainer/{id}/upper`
   - workdir: `/var/lib/mycontainer/{id}/work`
   - merged: `/var/lib/mycontainer/{id}/merged`

3. **`run_container()`** - основная логика:
   - Создает скрипт инициализации, который монтирует proc и устанавливает hostname
   - Использует `unshare` с флагами `--pid`, `--mount`, `--uts` для создания namespaces
   - Выполняет `chroot` в merged директорию
   - Запускает команду через `exec`, делая её PID 1
   - Ожидает завершения (foreground режим)

4. **Монтирование /proc** - реализовано через `mount -t proc proc /proc` внутри скрипта инициализации

**Делаем файл исполняемымм**
```bash
chmod +x mycontainer.py
```

---

### 6. Проверка выполнения требований

#### 6.1 Проверка создания директории

Запустим контейнер и проверим, что директория создалась с нужными папками

<img width="769" height="294" alt="image" src="https://github.com/user-attachments/assets/bfe6e45c-8aba-4ca9-b343-07bc5b937ea2" />

✅ Директория `/var/lib/mycontainer/test1` создана, внутри присутствуют папки upper, work, mergedс

---

#### 6.2 Проверка UTS namespace (hostname)

Проверим, что внутри контейнера hostname устанавливается из config.json и изолирован от хоста.

<img width="583" height="673" alt="image" src="https://github.com/user-attachments/assets/91a73b74-2560-4376-bd0f-87edd51d041e" />

✅ Внутри контейнера hostname = "mycontainer" (из config.json), на хосте другое значение. UTS namespace работает, hostname изолирован

---

#### 6.3 Проверка PID namespace

Проверим, что процессы внутри контейнера изолированы.  Сравним количество процессов на хосте и внутри контейнера

<img width="610" height="725" alt="image" src="https://github.com/user-attachments/assets/cd764fa1-90c8-4a9d-912c-5c36b0e28dc2" />

Вывод: Внутри контейнера виден только 1 процесс, в то время как на хосте их 353 -->(следовательно) PID namespace изолирует процессы

---

#### 6.4 Проверка overlayfs и сохранения изменений

Проверим, что изменения, сделанные в контейнере, сохраняются в upperdir, а базовый rootfs остается неизменным.

<img width="948" height="410" alt="image" src="https://github.com/user-attachments/assets/6cbea24b-5b6f-4b70-8f18-529823906a36" />

1) cat /data.txt в контейнере показывает содержимое из merged (объединение lower с upper)
2) cat upper/data.txt на хосте показывает, что файл физически лежит в upperdir, слое куда записываются изменения
3) ls rootfs/ | grep data.txt пуст —  тк базовый образ Alpine не был изменен (lowerdir только для чтения)

В итотге: Файл создан внутри контейнера. Файл сохранен в /var/lib/mycontainer/test4/upper/data.txt. Базовый Alpine rootfs остался неизменным. Overlayfs работает корректно

#### 6.5 Проверка монтирования /proc

Проверим, что внутри контейнера смонтирована файловая система /proc  для работы утилит (типа ps)

<img width="960" height="311" alt="image" src="https://github.com/user-attachments/assets/4165a625-d69f-43f5-94bf-dd3f5385863f" />

- Команда mount показывает: /proc смонтирован как файловая система типа proc
- Команда ls /proc/ выводит список файлов и директорий, подтверждая доступность

---

#### 6.6 Проверка foreground режима

Проверим, что утилита ожидает завершения команды.

```bash
time sudo python3 mycontainer.py --config config.json --id fg_test /bin/sleep 2
```

<img width="957" height="233" alt="image" src="https://github.com/user-attachments/assets/b4daeb59-82f4-4edf-b827-a578aeab1c74" />

Видночто утилита "зависнет" на 2 секунды, а затем завершится --> foreground режим — утилита ждет, пока команда внутри контейнера не выполнится

---

#### 6.7 Проверка, что команда становится PID 1

Проверим, что запускаемая команда имеет PID 1 внутри контейнера.

**Выполненная команда:**
```bash
sudo python3 mycontainer.py --config config.json --id test7 /bin/sh -c "ps aux | head -5"
```

<img width="965" height="427" alt="image" src="https://github.com/user-attachments/assets/750e5ca4-31f1-4c36-bb9c-8031b6cd57c6" />


Процесс init.sh имеет PID 1 внутри контейнера — это скрипт инициализации, который монтирует /proc и устанавливает hostname, внутри него выполняется наша команда (ps aux | head -5), а все процессы внутри контейнера имеют свои PID, начинающиеся с 1

---

### Вывод
В ходе выполнения лабораторной работы разработана утилита mycontainer.py, читающая конфигурацию из config.json, создающая изолированное окружение с помощью PID, Mount и UTS namespaces, настраивающая overlayfs (lowerdir — Alpine Linux, upperdir — хранилище изменений для каждого контейнера), запускающая команду как PID 1 в foreground режиме и монтирующая /proc для работы утилит типа ps
