"""
DeepSeekProvider с интеграцией subagents.

Улучшенный провайдер, который автоматически вызывает агенты
для сложных задач и интегрирует их результаты.
"""

import logging
from typing import Optional, List, Dict, Tuple, Any
import asyncio
import re

from .deepseek_provider import DeepSeekProvider
from .base import LLMProvider

logger = logging.getLogger(__name__)


class DeepSeekWithAgents(DeepSeekProvider):
    """
    DeepSeek провайдер с автоматической интеграцией агентов.
    
    Возможности:
    - Автоматическое определение нужных агентов
    - Параллельный вызов агентов
    - Компоновка результатов агентов
    - Умное планирование использования агентов
    """

    def __init__(
        self,
        api_key: str,
        agents_orchestrator,
        model: str = "deepseek-chat",
        timeout: int = 30,
        temperature: float = 0.9,
        max_tokens: int = 2000,
        rag_manager=None,
        enable_agent_planning: bool = True,
        max_agent_calls_per_request: int = 3
    ):
        """
        Инициализация DeepSeekWithAgents.

        Args:
            api_key: API ключ DeepSeek
            agents_orchestrator: Орчестратор агентов
            model: Название модели
            timeout: Таймаут запроса
            temperature: Температура генерации
            max_tokens: Максимальное количество токенов
            rag_manager: Менеджер RAG
            enable_agent_planning: Включить планирование агентов
            max_agent_calls_per_request: Максимум вызовов агентов на запрос
        """
        super().__init__(
            api_key=api_key,
            model=model,
            timeout=timeout,
            temperature=temperature,
            max_tokens=max_tokens,
            rag_manager=rag_manager
        )
        
        self.orchestrator = agents_orchestrator
        self.enable_agent_planning = enable_agent_planning
        self.max_agent_calls_per_request = max_agent_calls_per_request
        
        # Статистика использования агентов
        self.agent_stats = {
            "total_requests": 0,
            "agent_calls": 0,
            "git_agent_calls": 0,
            "docs_agent_calls": 0,
            "help_agent_calls": 0,
            "parallel_calls": 0,
            "agent_errors": 0
        }

        # Правила для определения нужных агентов
        self.agent_rules = {
            "git": {
                "keywords": ["git", "commit", "branch", "pull request", "push", "merge", "repository", "repo"],
                "patterns": [r"\bgit\b", r"\bcommit\b", r"\bbranch\b", r"\bpr\b"],
                "agents": ["git_agent"]
            },
            "docs": {
                "keywords": ["документация", "как использовать", "инструкция", "руководство", "help", "docs"],
                "patterns": [r"\bдокументация\b", r"\bкак\b.*\bиспользовать\b", r"\bhelp\b"],
                "agents": ["docs_agent"]
            },
            "help": {
                "keywords": ["помощь", "команды", "что умеет", "возможности", "функции"],
                "patterns": [r"\bпомощь\b", r"\bкоманды\b", r"\bчто\b.*\bумеет\b"],
                "agents": ["help_command_agent"]
            },
            "code": {
                "keywords": ["код", "программа", "функция", "класс", "алгоритм"],
                "patterns": [r"\bкод\b", r"\bпрограмма\b", r"\bфункция\b", r"\bкласс\b"],
                "agents": ["code_search_tool"]
            }
        }

        logger.info(f"DeepSeekWithAgents initialized with agent planning: {enable_agent_planning}")

    async def generate_response(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[str]:
        """
        Генерация ответа с автоматическим вызовом агентов.

        Args:
            user_message: Сообщение от пользователя
            system_prompt: Системный промпт
            conversation_history: История диалога

        Returns:
            Ответ от DeepSeek с учетом результатов агентов
        """
        self.agent_stats["total_requests"] += 1
        
        try:
            # 1. Анализ запроса для определения нужных агентов
            agent_plan = await self._plan_agent_usage(user_message)
            
            if not agent_plan["needs_agents"]:
                # Агенты не нужны, обычная генерация
                return await super().generate_response(
                    user_message, system_prompt, conversation_history
                )
            
            # 2. Вызов агентов
            agent_results = await self._execute_agents(agent_plan["agents"])
            
            # 3. Обогащение промпта результатами агентов
            enriched_system_prompt = self._create_enriched_prompt(
                system_prompt, agent_results
            )
            
            # 4. Генерация ответа с результатами агентов
            return await super().generate_response(
                user_message, enriched_system_prompt, conversation_history
            )
            
        except Exception as e:
            logger.error(f"Error in DeepSeekWithAgents.generate_response: {e}")
            # Fallback к обычной генерации
            return await super().generate_response(
                user_message, system_prompt, conversation_history
            )

    async def generate_response_with_sources(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[Optional[str], List[Dict]]:
        """
        Генерация ответа с источниками и агентами.

        Args:
            user_message: Сообщение от пользователя
            system_prompt: Системный промпт
            conversation_history: История диалога

        Returns:
            Кортеж (ответ, источники)
        """
        self.agent_stats["total_requests"] += 1
        
        try:
            # 1. Анализ запроса для определения нужных агентов
            agent_plan = await self._plan_agent_usage(user_message)
            
            # 2. Вызов агентов
            agent_results = []
            if agent_plan["needs_agents"]:
                agent_results = await self._execute_agents(agent_plan["agents"])
            
            # 3. Получение RAG источников
            rag_sources = []
            if self.rag_manager:
                try:
                    enriched_message, rag_sources = self.rag_manager.enrich_message_with_rag(
                        user_message, 
                        use_reranking=True
                    )
                except Exception as e:
                    logger.error(f"Error enriching message with RAG: {e}")
            
            # 4. Обогащение промпта результатами агентов и RAG
            enriched_system_prompt = self._create_enriched_prompt(
                system_prompt, agent_results, rag_sources
            )
            
            # 5. Обогащение сообщения пользователя
            enriched_user_message = user_message
            if agent_results:
                enriched_user_message = self._create_enriched_user_message(
                    user_message, agent_results, rag_sources
                )
            
            # 6. Генерация ответа
            response, final_sources = await super().generate_response_with_sources(
                enriched_user_message, enriched_system_prompt, conversation_history
            )
            
            # 7. Добавление информации о вызванных агентах
            if agent_results:
                agent_info = self._format_agent_results(agent_results)
                if response:
                    response += f"\n\n{agent_info}"
            
            return response, final_sources
            
        except Exception as e:
            logger.error(f"Error in DeepSeekWithAgents.generate_response_with_sources: {e}")
            # Fallback к обычной генерации
            return await super().generate_response_with_sources(
                user_message, system_prompt, conversation_history
            )

    async def _plan_agent_usage(self, query: str) -> Dict[str, Any]:
        """
        Определяет каких агентов нужно вызвать для запроса.

        Args:
            query: Пользовательский запрос

        Returns:
            План использования агентов
        """
        if not self.enable_agent_planning or not self.orchestrator:
            return {"needs_agents": False, "agents": []}
        
        query_lower = query.lower()
        needed_agents = set()
        confidence_scores = {}
        
        # Проверяем правила для каждого типа агентов
        for agent_type, rule in self.agent_rules.items():
            score = 0
            
            # Проверяем ключевые слова
            for keyword in rule["keywords"]:
                if keyword in query_lower:
                    score += 2
            
            # Проверяем паттерны
            for pattern in rule["patterns"]:
                if re.search(pattern, query_lower):
                    score += 3
            
            # Если есть совпадения, добавляем агентов
            if score > 0:
                for agent in rule["agents"]:
                    needed_agents.add(agent)
                    confidence_scores[agent] = score
        
        # Ограничиваем количество агентов
        if len(needed_agents) > self.max_agent_calls_per_request:
            # Сортируем по уверенности и берем топ N
            sorted_agents = sorted(
                confidence_scores.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            needed_agents = set(agent for agent, _ in sorted_agents[:self.max_agent_calls_per_request])
        
        return {
            "needs_agents": len(needed_agents) > 0,
            "agents": list(needed_agents),
            "confidence_scores": confidence_scores
        }

    async def _execute_agents(self, agent_names: List[str]) -> List[Dict[str, Any]]:
        """
        Выполняет агентов (параллельно если возможно).

        Args:
            agent_names: Список имен агентов для вызова

        Returns:
            Список результатов выполнения агентов
        """
        if not agent_names or not self.orchestrator:
            return []
        
        logger.info(f"Executing agents: {agent_names}")
        self.agent_stats["agent_calls"] += len(agent_names)
        
        results = []
        
        # Определяем агенты, которые можно вызывать параллельно
        parallel_agents = []
        sequential_agents = []
        
        for agent_name in agent_names:
            if agent_name in ["git_agent", "docs_agent"]:
                # Эти агенты можно вызывать параллельно
                parallel_agents.append(agent_name)
            else:
                # Другие агенты вызываем последовательно
                sequential_agents.append(agent_name)
        
        # Параллельный вызов
        if parallel_agents:
            self.agent_stats["parallel_calls"] += len(parallel_agents)
            parallel_results = await self._call_agents_parallel(parallel_agents)
            results.extend(parallel_results)
        
        # Последовательный вызов
        for agent_name in sequential_agents:
            try:
                result = await self._call_single_agent(agent_name)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error calling agent {agent_name}: {e}")
                self.agent_stats["agent_errors"] += 1
        
        # Обновляем статистику
        for agent_name in agent_names:
            if "git" in agent_name:
                self.agent_stats["git_agent_calls"] += 1
            elif "docs" in agent_name:
                self.agent_stats["docs_agent_calls"] += 1
            elif "help" in agent_name:
                self.agent_stats["help_agent_calls"] += 1
        
        return results

    async def _call_agents_parallel(self, agent_names: List[str]) -> List[Dict[str, Any]]:
        """
        Вызывает агенты параллельно.

        Args:
            agent_names: Список имен агентов

        Returns:
            Список результатов
        """
        tasks = []
        
        for agent_name in agent_names:
            task = asyncio.create_task(
                self._call_single_agent(agent_name)
            )
            tasks.append(task)
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Обрабатываем результаты
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Agent {agent_names[i]} failed: {result}")
                    self.agent_stats["agent_errors"] += 1
                elif result:
                    processed_results.append(result)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Error in parallel agent execution: {e}")
            return []

    async def _call_single_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Вызывает один агент.

        Args:
            agent_name: Имя агента

        Returns:
            Результат выполнения агента
        """
        try:
            # Формируем задачу для агента
            task = {
                "agent": agent_name,
                "action": self._get_agent_action(agent_name),
                "params": self._get_agent_params(agent_name)
            }
            
            # Вызываем агента через оркестратор
            result = await self.orchestrator.execute_agent_task(task)
            
            return {
                "agent": agent_name,
                "success": result.get("success", False),
                "data": result.get("data"),
                "error": result.get("error"),
                "execution_time": result.get("execution_time", 0)
            }
            
        except Exception as e:
            logger.error(f"Error calling agent {agent_name}: {e}")
            return {
                "agent": agent_name,
                "success": False,
                "error": str(e),
                "data": None
            }

    def _get_agent_action(self, agent_name: str) -> str:
        """Определяет действие для агента."""
        action_map = {
            "git_agent": "get_repo_status",
            "docs_agent": "search_documents",
            "help_command_agent": "get_commands",
            "code_search_tool": "search_code"
        }
        
        return action_map.get(agent_name, "execute")

    def _get_agent_params(self, agent_name: str) -> Dict[str, Any]:
        """Определяет параметры для агента."""
        params_map = {
            "git_agent": {"detailed": True},
            "docs_agent": {"limit": 5},
            "help_command_agent": {},
            "code_search_tool": {"limit": 10}
        }
        
        return params_map.get(agent_name, {})

    def _create_enriched_prompt(
        self,
        system_prompt: str,
        agent_results: List[Dict[str, Any]],
        rag_sources: Optional[List[Dict]] = None
    ) -> str:
        """
        Создает обогащенный системный промпт.

        Args:
            system_prompt: Оригинальный системный промпт
            agent_results: Результаты выполнения агентов
            rag_sources: Источники RAG

        Returns:
            Обогащенный системный промпт
        """
        enriched = system_prompt
        
        if agent_results:
            enriched += "\n\n# Результаты выполнения агентов:\n"
            
            for result in agent_results:
                if result["success"]:
                    enriched += f"## {result['agent']}:\n{result['data']}\n\n"
                else:
                    enriched += f"## {result['agent']} (ошибка):\n{result['error']}\n\n"
        
        if rag_sources:
            enriched += "\n# Релевантная информация из документации:\n"
            for i, source in enumerate(rag_sources[:5], 1):
                enriched += f"{i}. {source.get('content', '')[:200]}...\n"
        
        enriched += "\nИспользуй эту информацию для формирования подробного и точного ответа."
        
        return enriched

    def _create_enriched_user_message(
        self,
        user_message: str,
        agent_results: List[Dict[str, Any]],
        rag_sources: Optional[List[Dict]] = None
    ) -> str:
        """
        Создает обогащенное сообщение пользователя.

        Args:
            user_message: Оригинальное сообщение
            agent_results: Результаты агентов
            rag_sources: Источники RAG

        Returns:
            Обогащенное сообщение
        """
        # В текущей реализации не изменяем сообщение пользователя,
        # только системный промпт
        return user_message

    def _format_agent_results(self, agent_results: List[Dict[str, Any]]) -> str:
        """
        Форматирует результаты агентов для вывода пользователю.

        Args:
            agent_results: Результаты выполнения агентов

        Returns:
            Отформатированная строка с результатами
        """
        if not agent_results:
            return ""
        
        formatted = "📋 **Результаты выполнения агентов:**\n\n"
        
        for result in agent_results:
            agent_name = result["agent"].replace("_", " ").title()
            
            if result["success"]:
                formatted += f"✅ **{agent_name}**: выполнен успешно\n"
                if result.get("execution_time"):
                    formatted += f"   Время выполнения: {result['execution_time']:.2f}с\n"
            else:
                formatted += f"❌ **{agent_name}**: ошибка выполнения\n"
                if result.get("error"):
                    formatted += f"   Ошибка: {result['error']}\n"
        
        return formatted

    def get_agent_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику использования агентов.

        Returns:
            Словарь со статистикой
        """
        return self.agent_stats.copy()

    def reset_agent_stats(self) -> None:
        """Сбрасывает статистику использования агентов."""
        self.agent_stats = {
            "total_requests": 0,
            "agent_calls": 0,
            "git_agent_calls": 0,
            "docs_agent_calls": 0,
            "help_agent_calls": 0,
            "parallel_calls": 0,
            "agent_errors": 0
        }
        logger.info("Agent stats reset")

    def update_agent_rules(self, new_rules: Dict[str, Any]) -> None:
        """
        Обновляет правила определения агентов.

        Args:
            new_rules: Новые правила для агентов
        """
        self.agent_rules.update(new_rules)
        logger.info(f"Agent rules updated: {list(new_rules.keys())}")

    def get_provider_name(self) -> str:
        """
        Получение имени провайдера.

        Returns:
            Строка "deepseek_with_agents"
        """
        return "deepseek_with_agents"

    def get_provider_info(self) -> Dict[str, Any]:
        """
        Возвращает информацию о провайдере.

        Returns:
            Словарь с информацией о провайдере
        """
        info = super().get_provider_info()
        info.update({
            "agent_integration": True,
            "agent_planning": self.enable_agent_planning,
            "max_agent_calls": self.max_agent_calls_per_request,
            "supported_agents": list(self.orchestrator.agents.keys()) if self.orchestrator else [],
            "agent_stats": self.get_agent_stats()
        })
        
        return info
