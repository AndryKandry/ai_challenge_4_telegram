#!/usr/bin/env python3
"""
Тесты для проверки персистентности данных в системе памяти.
Проверяет корректность сохранения и извлечения данных из SQLite базы.
"""

import json
import os
import sys
import unittest
from pathlib import Path

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.memory_manager import MemoryManager


class TestMemoryPersistence(unittest.TestCase):
    """Тесты персистентности данных MemoryManager."""

    def setUp(self):
        """Подготовка перед каждым тестом."""
        self.test_db = "test_memory.db"
        self.memory = MemoryManager(self.test_db)
        self.memory.create_tables()

        # Тестовые данные
        self.test_user_id = 12345
        self.test_chat_id = 67890

    def tearDown(self):
        """Очистка после каждого теста."""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_save_and_retrieve_message(self):
        """Тест сохранения и извлечения сообщения."""
        message_text = "Тестовое сообщение пользователя"

        # Сохраняем сообщение
        message_id = self.memory.save_message(
            self.test_user_id,
            self.test_chat_id,
            message_text,
            "user"
        )

        self.assertIsNotNone(message_id)
        self.assertGreater(message_id, 0)

        # Извлекаем историю
        history = self.memory.get_conversation_history(
            self.test_user_id,
            self.test_chat_id
        )

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["message_text"], message_text)
        self.assertEqual(history[0]["message_type"], "user")
        self.assertEqual(history[0]["user_id"], self.test_user_id)
        self.assertEqual(history[0]["chat_id"], self.test_chat_id)

    def test_persistence_across_instances(self):
        """Тест сохранения данных между разными экземплярами (перезапуск бота)."""
        # Первый экземпляр - сохраняем сообщение
        memory1 = MemoryManager(self.test_db)
        memory1.save_message(
            self.test_user_id,
            self.test_chat_id,
            "Первое сообщение",
            "user"
        )
        del memory1

        # Второй экземпляр (имитация перезапуска бота)
        memory2 = MemoryManager(self.test_db)
        history = memory2.get_conversation_history(
            self.test_user_id,
            self.test_chat_id
        )

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["message_text"], "Первое сообщение")

    def test_multiple_users(self):
        """Тест работы с несколькими пользователями."""
        user1_id = 111
        user2_id = 222
        chat_id = 333

        # Сохраняем сообщения от разных пользователей
        self.memory.save_message(user1_id, chat_id, "Сообщение от пользователя 1", "user")
        self.memory.save_message(user2_id, chat_id, "Сообщение от пользователя 2", "user")

        # Проверяем, что сообщения не смешиваются
        history1 = self.memory.get_conversation_history(user1_id, chat_id)
        history2 = self.memory.get_conversation_history(user2_id, chat_id)

        self.assertEqual(len(history1), 1)
        self.assertEqual(len(history2), 1)
        self.assertEqual(history1[0]["message_text"], "Сообщение от пользователя 1")
        self.assertEqual(history2[0]["message_text"], "Сообщение от пользователя 2")

    def test_conversation_history_limit(self):
        """Тест ограничения количества сообщений в истории."""
        # Сохраняем 10 сообщений
        for i in range(10):
            self.memory.save_message(
                self.test_user_id,
                self.test_chat_id,
                f"Сообщение {i}",
                "user" if i % 2 == 0 else "assistant"
            )

        # Запрашиваем последние 5
        history = self.memory.get_conversation_history(
            self.test_user_id,
            self.test_chat_id,
            limit=5
        )

        # Проверяем, что получили ровно 5 сообщений (limit работает)
        self.assertEqual(len(history), 5)
        # Проверяем, что все сообщения содержат правильный текст
        for msg in history:
            self.assertIn("Сообщение", msg["message_text"])

    def test_save_intermediate_result(self):
        """Тест сохранения промежуточных результатов."""
        task_name = "test_task"
        result_data = {"key": "value", "number": 42}

        # Сохраняем результат
        result_id = self.memory.save_intermediate_result(
            self.test_user_id,
            self.test_chat_id,
            task_name,
            result_data,
            status="completed"
        )

        self.assertIsNotNone(result_id)

        # Извлекаем результаты
        results = self.memory.get_intermediate_results(
            self.test_user_id,
            self.test_chat_id,
            task_name=task_name
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["task_name"], task_name)
        self.assertEqual(results[0]["status"], "completed")
        self.assertEqual(results[0]["result_data"], result_data)

    def test_update_intermediate_result_status(self):
        """Тест обновления статуса промежуточного результата."""
        # Создаем результат со статусом pending
        result_id = self.memory.save_intermediate_result(
            self.test_user_id,
            self.test_chat_id,
            "task",
            {"data": "test"},
            status="pending"
        )

        # Обновляем статус на completed
        success = self.memory.update_intermediate_result_status(
            result_id,
            "completed",
            {"data": "test", "result": "success"}
        )

        self.assertTrue(success)

        # Проверяем обновление
        results = self.memory.get_intermediate_results(
            self.test_user_id,
            self.test_chat_id
        )

        self.assertEqual(results[0]["status"], "completed")
        self.assertEqual(results[0]["result_data"]["result"], "success")

    def test_save_and_retrieve_action(self):
        """Тест сохранения и извлечения действий агента."""
        action_id = self.memory.save_action(
            user_id=self.test_user_id,
            chat_id=self.test_chat_id,
            action_type="api_call",
            description="Вызов API",
            input_data={"param": "value"},
            output_data={"status": "success"},
            execution_time=150
        )

        self.assertIsNotNone(action_id)

        # Извлекаем историю действий
        actions = self.memory.get_actions_history(
            self.test_user_id,
            self.test_chat_id
        )

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["action_type"], "api_call")
        self.assertEqual(actions[0]["execution_time_ms"], 150)
        self.assertEqual(actions[0]["input_data"]["param"], "value")

    def test_save_and_retrieve_knowledge(self):
        """Тест сохранения и извлечения знаний."""
        # Сохраняем факт
        knowledge_id = self.memory.save_knowledge(
            user_id=self.test_user_id,
            entity_type="preference",
            key="favorite_color",
            value="blue",
            confidence=0.95
        )

        self.assertIsNotNone(knowledge_id)

        # Извлекаем знания
        knowledge = self.memory.get_knowledge(
            user_id=self.test_user_id,
            entity_type="preference"
        )

        self.assertEqual(len(knowledge), 1)
        self.assertEqual(knowledge[0]["entity_key"], "favorite_color")
        self.assertEqual(knowledge[0]["entity_value"], "blue")
        self.assertEqual(knowledge[0]["confidence_score"], 0.95)

    def test_knowledge_unique_constraint(self):
        """Тест уникальности знаний (обновление при конфликте)."""
        # Сохраняем знание
        self.memory.save_knowledge(
            user_id=self.test_user_id,
            entity_type="name",
            key="first_name",
            value="Иван"
        )

        # Пытаемся сохранить знание с тем же ключом (должно обновиться)
        self.memory.save_knowledge(
            user_id=self.test_user_id,
            entity_type="name",
            key="first_name",
            value="Петр"
        )

        # Проверяем, что осталось только одно знание с новым значением
        knowledge = self.memory.get_knowledge(
            user_id=self.test_user_id,
            entity_type="name"
        )

        self.assertEqual(len(knowledge), 1)
        self.assertEqual(knowledge[0]["entity_value"], "Петр")

    def test_session_management(self):
        """Тест управления сессиями."""
        # Создаем сессию
        session_id = self.memory.create_session(
            self.test_user_id,
            self.test_chat_id
        )

        self.assertIsNotNone(session_id)

        # Проверяем активную сессию
        active_session = self.memory.get_active_session(
            self.test_user_id,
            self.test_chat_id
        )

        self.assertEqual(active_session, session_id)

        # Завершаем сессию
        success = self.memory.end_session(session_id)
        self.assertTrue(success)

        # Проверяем, что активной сессии больше нет
        active_session = self.memory.get_active_session(
            self.test_user_id,
            self.test_chat_id
        )

        self.assertIsNone(active_session)

    def test_statistics(self):
        """Тест получения статистики."""
        # Добавляем различные данные
        self.memory.save_message(self.test_user_id, self.test_chat_id, "msg1", "user")
        self.memory.save_message(self.test_user_id, self.test_chat_id, "msg2", "assistant")
        self.memory.save_intermediate_result(self.test_user_id, self.test_chat_id, "task", {"data": 1})
        self.memory.save_action(self.test_user_id, self.test_chat_id, "test", "test action")
        self.memory.save_knowledge(self.test_user_id, "fact", "key", "value")

        # Получаем статистику для пользователя
        stats = self.memory.get_statistics(user_id=self.test_user_id)

        self.assertEqual(stats["messages_count"], 2)
        self.assertEqual(stats["intermediate_results_count"], 1)
        self.assertEqual(stats["actions_count"], 1)
        self.assertEqual(stats["knowledge_count"], 1)

    def test_clear_user_history(self):
        """Тест очистки истории пользователя."""
        # Добавляем сообщения
        for i in range(5):
            self.memory.save_message(
                self.test_user_id,
                self.test_chat_id,
                f"Сообщение {i}",
                "user"
            )

        # Проверяем, что сообщения сохранены
        history = self.memory.get_conversation_history(
            self.test_user_id,
            self.test_chat_id
        )
        self.assertEqual(len(history), 5)

        # Очищаем историю
        success = self.memory.clear_user_history(
            self.test_user_id,
            self.test_chat_id
        )
        self.assertTrue(success)

        # Проверяем, что история пуста
        history = self.memory.get_conversation_history(
            self.test_user_id,
            self.test_chat_id
        )
        self.assertEqual(len(history), 0)

    def test_export_conversation_history(self):
        """Тест экспорта истории диалога."""
        # Добавляем сообщения
        self.memory.save_message(self.test_user_id, self.test_chat_id, "Вопрос", "user")
        self.memory.save_message(self.test_user_id, self.test_chat_id, "Ответ", "assistant")

        # Экспорт в JSON
        json_export = self.memory.export_conversation_history(
            self.test_user_id,
            self.test_chat_id,
            format='json'
        )
        self.assertIsNotNone(json_export)
        data = json.loads(json_export)
        self.assertEqual(len(data), 2)

        # Экспорт в текст
        text_export = self.memory.export_conversation_history(
            self.test_user_id,
            self.test_chat_id,
            format='text'
        )
        self.assertIsNotNone(text_export)
        self.assertIn("Пользователь", text_export)
        self.assertIn("Ассистент", text_export)

        # Экспорт в CSV
        csv_export = self.memory.export_conversation_history(
            self.test_user_id,
            self.test_chat_id,
            format='csv'
        )
        self.assertIsNotNone(csv_export)
        self.assertIn("message_type", csv_export)


class TestMemoryManagerErrorHandling(unittest.TestCase):
    """Тесты обработки ошибок MemoryManager."""

    def setUp(self):
        """Подготовка перед каждым тестом."""
        self.test_db = "test_memory_errors.db"
        self.memory = MemoryManager(self.test_db)
        self.memory.create_tables()

    def tearDown(self):
        """Очистка после каждого теста."""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_invalid_message_type(self):
        """Тест обработки неверного типа сообщения."""
        with self.assertRaises(ValueError):
            self.memory.save_message(
                user_id=123,
                chat_id=456,
                message="Test",
                message_type="invalid_type"
            )

    def test_invalid_result_status(self):
        """Тест обработки неверного статуса результата."""
        with self.assertRaises(ValueError):
            self.memory.save_intermediate_result(
                user_id=123,
                chat_id=456,
                task_name="test",
                result_data={"data": "test"},
                status="invalid_status"
            )

    def test_empty_database_statistics(self):
        """Тест получения статистики из пустой БД."""
        stats = self.memory.get_statistics(user_id=99999)

        self.assertEqual(stats["messages_count"], 0)
        self.assertEqual(stats["intermediate_results_count"], 0)
        self.assertEqual(stats["actions_count"], 0)
        self.assertEqual(stats["knowledge_count"], 0)


def run_tests():
    """Запуск всех тестов."""
    # Создаем набор тестов
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestMemoryPersistence))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryManagerErrorHandling))

    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Возвращаем код выхода
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
