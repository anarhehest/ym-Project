# Введение
Простой потоковый радио‑сервер на Flask, который берёт треки из Yandex.Music,
буферизует их в кольцевом буфере и отдаёт по HTTP (audio/mpeg).
Метаданные передаются по SSE для корректного отображения обложки и названия.

Включает интеграцию с [yandex_music](https://pypi.org/project/yandex-music/) и 
минимальный фронтенд для показа обложки и метаданных.

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

