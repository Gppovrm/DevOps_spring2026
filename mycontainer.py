#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import argparse
from pathlib import Path

def load_config(config_path):
    """Загружает конфиг из JSON файла"""
    with open(config_path, 'r') as f:
        return json.load(f)

def setup_container_dirs(container_id):
    """Создает директории для контейнера"""
    base_path = Path(f"/var/lib/mycontainer/{container_id}")
    
    # Создаем все нужные директории
    base_path.mkdir(parents=True, exist_ok=True)
    (base_path / "upper").mkdir(exist_ok=True)
    (base_path / "work").mkdir(exist_ok=True)
    (base_path / "merged").mkdir(exist_ok=True)
    
    return base_path

def mount_overlayfs(container_id, base_path):
    """Монтирует overlayfs"""
    rootfs_base = "/var/lib/mycontainer/rootfs"
    merged_path = base_path / "merged"
    
    # Параметры монтирования overlayfs
    options = f"lowerdir={rootfs_base},upperdir={base_path}/upper,workdir={base_path}/work"
    
    # Монтируем
    subprocess.run(["mount", "-t", "overlay", "overlay", "-o", options, str(merged_path)], check=True)
    
    return merged_path

def run_container(container_id, command, hostname):
    """Запускает команду в контейнере"""
    
    # Создаем директории
    base_path = setup_container_dirs(container_id)
    
    # Монтируем overlayfs
    merged_path = mount_overlayfs(container_id, base_path)
    
    print(f"[+] Контейнер {container_id} запущен")
    print(f"[+] Команда: {' '.join(command)}")
    print(f"[+] Hostname: {hostname}")
    print("[*] Ожидание завершения...")
    
    # Формируем команду для запуска внутри контейнера
    container_cmd = [
        "unshare",
        "--fork",
        "--pid",
        "--mount",
        "--uts",
        "--mount-proc",
        "chroot", str(merged_path),
        "/bin/sh", "-c", f"hostname {hostname} && exec {' '.join(command)}"
    ]
    
    # Запускаем и ждем завершения
    process = subprocess.Popen(container_cmd)
    process.wait()
    
    print(f"[+] Контейнер завершил работу с кодом {process.returncode}")
    
    # Размонтируем overlayfs
    subprocess.run(["umount", str(merged_path)], check=False)
    
    return process.returncode

def main():
    parser = argparse.ArgumentParser(description='Простой контейнерный рантайм')
    parser.add_argument('--config', '-c', required=True, help='Путь к config.json')
    parser.add_argument('--id', required=True, help='ID контейнера')
    parser.add_argument('cmd', nargs=argparse.REMAINDER, help='Команда для выполнения')
    
    args = parser.parse_args()
    
    # Проверяем root права
    if os.geteuid() != 0:
        print("[-] Ошибка: нужны права root!")
        print("Запустите: sudo python3 mycontainer.py ...")
        sys.exit(1)
    
    # Проверяем, что команда передана
    if not args.cmd:
        print("[-] Ошибка: не указана команда")
        sys.exit(1)
    
    # Загружаем конфиг
    config = load_config(args.config)
    hostname = config.get('hostname', 'container')
    
    # Запускаем контейнер
    exit_code = run_container(args.id, args.cmd, hostname)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
