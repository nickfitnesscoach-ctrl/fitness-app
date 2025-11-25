# Тестирование функционала аватара

## ✅ Результаты тестов

**Все 13 тестов прошли успешно!**

```
Ran 13 tests in 0.175s
OK
```

## Запуск тестов

### Запустить все тесты аватара (с SQLite для скорости):
```bash
cd backend
python manage.py test apps.users.tests.test_avatar_upload --settings=config.settings.test
```

### Запустить с PostgreSQL (если настроен):
```bash
cd backend
python manage.py test apps.users.tests.test_avatar_upload
```

### Запустить конкретный тест-кейс:
```bash
python manage.py test apps.users.tests.test_avatar_upload.AvatarUploadTest
```

### Запустить один конкретный тест:
```bash
python manage.py test apps.users.tests.test_avatar_upload.AvatarUploadTest.test_upload_avatar_success_jpeg
```

### Запустить с подробным выводом:
```bash
python manage.py test apps.users.tests.test_avatar_upload --verbosity=2
```

## Что тестируется

### Успешные сценарии:
- ✅ Загрузка JPEG аватара
- ✅ Загрузка PNG аватара
- ✅ Загрузка WebP аватара
- ✅ Замена старого аватара новым
- ✅ Генерация avatar_url в ответе
- ✅ Получение avatar_url через GET /profile/

### Валидация и ошибки:
- ✅ Отклонение файлов > 5 МБ
- ✅ Отклонение неверных MIME типов (не изображение)
- ✅ Ошибка при отсутствии файла
- ✅ Требование авторизации (401 без авторизации)

### Serializer:
- ✅ Генерация полного URL с request context
- ✅ Генерация относительного URL без context
- ✅ Возврат null когда аватара нет

## Покрытие

Тесты покрывают:
- Model: Profile.avatar поле
- View: UploadAvatarView
- Serializer: ProfileSerializer.get_avatar_url()
- API endpoint: POST /api/v1/users/profile/avatar/

## Ручное тестирование через curl

### 1. Загрузить аватар:
```bash
curl -X POST http://localhost:8000/api/v1/users/profile/avatar/ \
  -H "X-Telegram-Id: 123456789" \
  -H "X-Telegram-First-Name: Test" \
  -F "avatar=@/path/to/image.jpg"
```

### 2. Получить профиль с avatar_url:
```bash
curl http://localhost:8000/api/v1/users/profile/ \
  -H "X-Telegram-Id: 123456789"
```

### 3. Проверить доступность аватара:
```bash
curl http://localhost:8000/media/avatars/test_avatar_xyz.jpg
```

## Что проверить вручную после деплоя

1. ✅ Загрузка аватара через Telegram mini-app
2. ✅ Отображение аватара после перезагрузки
3. ✅ Доступность URL аватара
4. ✅ Права доступа к папке /media/avatars/
5. ✅ Валидация размера файла (попробовать >5 МБ)
6. ✅ Валидация формата (попробовать загрузить .txt)
