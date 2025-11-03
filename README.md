# Введение
Простой потоковый радио‑сервер на Flask, который берёт треки из Yandex.Music,
буферизует их в кольцевом буфере и отдаёт по HTTP (audio/mpeg).
Метаданные передаются по SSE для корректного отображения обложки и названия.

Включает интеграцию с [yandex_music](https://pypi.org/project/yandex-music/) и 
минимальный фронтенд для показа обложки и метаданных.

<img width="1569" height="1036" alt="Screenshot 2025-11-03 at 17 55 26" src="https://github.com/user-attachments/assets/ffe9a664-9083-46f9-a81a-553b992b06ed" />

## Использование
Клонируйте репозиторий:
```bash
git clone https://github.com/anarhehest/ym-Project.git
cd ym\-Project
```
Создайте файл .env рядом с docker-compose.yml:
```Code
YM_TOKEN="your_token"
```
Запустите проект:
```
make
```

