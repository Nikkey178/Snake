# logic_optimized.py
"""Optimized heuristic logic with <500ms response time.

Optimizations:
1. Caching expensive computations
2. Early termination in evaluation
3. Lazy evaluation of features
4. Precomputed constants
5. Time-bounded search
"""

import time
from collections import deque
from typing import Dict, List, Optional, Set, Tuple, Any
from functools import lru_cache
import random
import math

# ============================================================================
# КОНСТАНТЫ И НАСТРОЙКИ
# ============================================================================

Point = Tuple[int, int]

DIRECTIONS: Dict[str, Point] = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}

# Лимиты времени
MAX_RESPONSE_TIME = 0.5  # 500ms
TIME_BUFFER = 0.05  # 50ms буфер для безопасности
EVALUATION_TIME_LIMIT = MAX_RESPONSE_TIME - TIME_BUFFER

# Конфигурация стратегии
class StrategyConfig:
    CRITICAL_HEALTH = 25
    LOW_HEALTH = 50
    GOOD_HEALTH = 80
    
    # Упрощенные веса для скорости
    SURVIVAL_WEIGHT = 3.0
    FOOD_WEIGHT = 2.0
    AGGRESSIVE_WEIGHT = 1.5
    TERRITORY_WEIGHT = 1.0
    
    # Ограничения для ускорения
    MAX_FLOOD_FILL = 20  # ограничение для flood fill
    MAX_LOOKAHEAD = 2    # уменьшенный горизонт планирования

# ============================================================================
# КЭШИРОВАНИЕ ДОРОГИХ ВЫЧИСЛЕНИЙ
# ============================================================================

class Cache:
    """Простой кэш для результатов вычислений."""
    
    def __init__(self, maxsize=128):
        self.cache = {}
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
    
    def get(self, key):
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None
    
    def set(self, key, value):
        if len(self.cache) >= self.maxsize:
            # Удаляем случайный элемент при переполнении
            self.cache.pop(next(iter(self.cache)))
        self.cache[key] = value
    
    def clear(self):
        self.cache.clear()
        self.hits = 0
        self.misses = 0

# Глобальный кэш для текущего хода
_turn_cache = Cache(maxsize=64)

# ============================================================================
# ОСНОВНАЯ ЛОГИКА ВЫБОРА ХОДА
# ============================================================================

def choose_move(game_state: Dict) -> str:
    """Оптимизированный выбор хода с таймаутом."""
    start_time = time.perf_counter()
    
    try:
        # Очищаем кэш для нового хода
        _turn_cache.clear()
        
        # Быстрый анализ контекста
        context = analyze_game_context_fast(game_state)
        
        # Получаем легальные ходы
        legal_moves = get_legal_moves_fast(game_state)
        if not legal_moves:
            return "up"
        
        # Если только один ход - возвращаем сразу
        if len(legal_moves) == 1:
            return legal_moves[0]
        
        # Оцениваем ходы с ограничением по времени
        best_move = legal_moves[0]
        best_score = -float('inf')
        
        for move in legal_moves:
            # Проверяем время
            if time.perf_counter() - start_time > EVALUATION_TIME_LIMIT:
                break
            
            score = evaluate_move_fast(game_state, move, context)
            if score > best_score:
                best_score = score
                best_move = move
        
        # Если время истекло, возвращаем лучший найденный ход
        return best_move
        
    except Exception:
        # Безопасный fallback
        return choose_move_safe(game_state)

def get_info() -> Dict[str, str]:
    return {
        "apiversion": "1",
        "author": "hackathon",
        "color": "#6434eb",
        "head": "smart-caterpillar",
        "tail": "weight",
        "version": "3.0.0",
    }

# ============================================================================
# БЫСТРЫЙ АНАЛИЗ КОНТЕКСТА
# ============================================================================

def analyze_game_context_fast(game_state: Dict) -> Dict:
    """Быстрый анализ контекста без тяжелых вычислений."""
    you = game_state["you"]
    board = game_state["board"]
    
    health = you["health"]
    
    # Статус здоровья (быстро)
    if health < StrategyConfig.CRITICAL_HEALTH:
        health_status = "critical"
    elif health < StrategyConfig.LOW_HEALTH:
        health_status = "low"
    elif health < StrategyConfig.GOOD_HEALTH:
        health_status = "moderate"
    else:
        health_status = "good"
    
    # Фаза игры (быстро)
    turn = game_state["turn"]
    num_snakes = len(board["snakes"])
    if turn < 20:
        phase = "early"
    elif num_snakes > 3:
        phase = "mid"
    else:
        phase = "late"
    
    # Определяем стратегию (упрощенно)
    if health_status == "critical":
        strategy = "desperate_food"
    elif health_status == "low":
        strategy = "seek_food"
    elif health_status == "good" and num_snakes <= 2:
        # Проверяем размер (быстро)
        my_length = you["length"]
        max_enemy = max((s["length"] for s in board["snakes"] if s["id"] != you["id"]), default=0)
        if my_length > max_enemy:
            strategy = "aggressive"
        else:
            strategy = "defensive"
    else:
        strategy = "balanced"
    
    return {
        "health_status": health_status,
        "phase": phase,
        "primary_strategy": strategy,
        "num_snakes": num_snakes,
        "food_count": len(board["food"])
    }

# ============================================================================
# БЫСТРЫЙ ПОЛУЧЕНИЕ ЛЕГАЛЬНЫХ ХОДОВ
# ============================================================================

def get_legal_moves_fast(game_state: Dict) -> List[str]:
    """Быстрое получение легальных ходов."""
    board = game_state["board"]
    you = game_state["you"]
    width, height = board["width"], board["height"]
    head = (you["head"]["x"], you["head"]["y"])
    
    # Кэшируем занятые клетки
    cache_key = ("occupied", id(game_state))
    occupied = _turn_cache.get(cache_key)
    if occupied is None:
        occupied = set()
        for snake in board["snakes"]:
            for seg in snake["body"]:
                occupied.add((seg["x"], seg["y"]))
        _turn_cache.set(cache_key, occupied)
    
    legal = []
    for move, (dx, dy) in DIRECTIONS.items():
        nx, ny = head[0] + dx, head[1] + dy
        if (0 <= nx < width and 0 <= ny < height and 
            (nx, ny) not in occupied):
            legal.append(move)
    
    return legal

# ============================================================================
# БЫСТРАЯ ОЦЕНКА ХОДА
# ============================================================================

def evaluate_move_fast(game_state: Dict, move: str, context: Dict) -> float:
    """Быстрая оценка хода с приоритетом скорости."""
    board = game_state["board"]
    you = game_state["you"]
    width, height = board["width"], board["height"]
    head = (you["head"]["x"], you["head"]["y"])
    dx, dy = DIRECTIONS[move]
    next_pos = (head[0] + dx, head[1] + dy)
    
    occupied = _turn_cache.get(("occupied", id(game_state)))
    if occupied is None:
        occupied = set()
        for snake in board["snakes"]:
            for seg in snake["body"]:
                occupied.add((seg["x"], seg["y"]))
        _turn_cache.set(("occupied", id(game_state)), occupied)
    
    # Базовые проверки безопасности (очень быстро)
    if next_pos in occupied:
        return -float('inf')
    
    # Основной счет (только ключевые факторы)
    score = 0.0
    
    # 1. Пространство для маневра (с ограничением)
    space = flood_fill_fast(next_pos, occupied, width, height, StrategyConfig.MAX_FLOOD_FILL)
    score += space * 2.0
    
    # 2. Еда (если нужно)
    if context["health_status"] in ["critical", "low"]:
        food_score = get_food_score_fast(game_state, next_pos, head)
        score += food_score * 3.0
    
    # 3. Опасность head-to-head (быстрая проверка)
    danger_score = check_head_to_head_fast(game_state, next_pos, you["length"])
    score += danger_score
    
    # 4. Контроль центра (очень быстро)
    center_dist = abs(next_pos[0] - (width - 1) / 2) + abs(next_pos[1] - (height - 1) / 2)
    score += (width + height - center_dist) * 0.5
    
    # 5. Агрессивная игра (если стратегия позволяет)
    if context["primary_strategy"] == "aggressive":
        agg_score = get_aggressive_score_fast(game_state, next_pos, you["length"])
        score += agg_score * 1.5
    
    return score

# ============================================================================
# ОПТИМИЗИРОВАННЫЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

@lru_cache(maxsize=256)
def flood_fill_fast_cached(start_x: int, start_y: int, 
                           occupied_hash: int, width: int, height: int, 
                           limit: int) -> int:
    """Кэшированная версия flood fill."""
    start = (start_x, start_y)
    # Восстанавливаем occupied из хэша (упрощенно)
    # В реальном коде нужно передавать множество
    return flood_fill_fast_impl(start, set(), width, height, limit)

def flood_fill_fast(start: Point, occupied: Set[Point], 
                    width: int, height: int, limit: int) -> int:
    """Быстрый flood fill с ограничением."""
    return flood_fill_fast_impl(start, occupied, width, height, limit)

def flood_fill_fast_impl(start: Point, occupied: Set[Point], 
                         width: int, height: int, limit: int) -> int:
    """Реализация flood fill с ранним выходом."""
    if start in occupied:
        return 0
    
    seen = {start}
    stack = [start]
    count = 0
    
    # Используем локальные переменные для скорости
    dirs = DIRECTIONS.values()
    
    while stack and count < limit:
        x, y = stack.pop()
        count += 1
        
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            nxt = (nx, ny)
            if (0 <= nx < width and 0 <= ny < height and 
                nxt not in seen and nxt not in occupied):
                seen.add(nxt)
                stack.append(nxt)
    
    return count

def get_food_score_fast(game_state: Dict, next_pos: Point, head: Point) -> float:
    """Быстрая оценка близости к еде."""
    foods = game_state["board"]["food"]
    if not foods:
        return 0.0
    
    # Находим минимальное расстояние (быстрый цикл)
    min_dist_next = float('inf')
    min_dist_head = float('inf')
    
    for food in foods:
        fx, fy = food["x"], food["y"]
        dist_next = abs(next_pos[0] - fx) + abs(next_pos[1] - fy)
        dist_head = abs(head[0] - fx) + abs(head[1] - fy)
        
        if dist_next < min_dist_next:
            min_dist_next = dist_next
        if dist_head < min_dist_head:
            min_dist_head = dist_head
    
    # Если движемся к еде
    if min_dist_next < min_dist_head:
        return (min_dist_head - min_dist_next) * 2.0
    
    # Если на клетке с едой
    if min_dist_next == 0:
        return 10.0
    
    return 0.0

def check_head_to_head_fast(game_state: Dict, next_pos: Point, my_length: int) -> float:
    """Быстрая проверка head-to-head столкновений."""
    you = game_state["you"]
    board = game_state["board"]
    
    # Проверяем только головы врагов (без полного обхода)
    for snake in board["snakes"]:
        if snake["id"] == you["id"]:
            continue
        if snake["length"] >= my_length:
            enemy_head = (snake["head"]["x"], snake["head"]["y"])
            # Проверяем, не движется ли враг на нашу клетку
            for dx, dy in DIRECTIONS.values():
                enemy_next = (enemy_head[0] + dx, enemy_head[1] + dy)
                if enemy_next == next_pos:
                    return -20.0  # опасность
            # Проверяем, не стоим ли мы на пути врага
            if enemy_head == next_pos:
                return 15.0  # можем съесть врага
    
    return 0.0

def get_aggressive_score_fast(game_state: Dict, next_pos: Point, my_length: int) -> float:
    """Быстрая оценка агрессивных действий."""
    you = game_state["you"]
    board = game_state["board"]
    score = 0.0
    
    for snake in board["snakes"]:
        if snake["id"] == you["id"]:
            continue
        if snake["length"] <= my_length:
            enemy_head = (snake["head"]["x"], snake["head"]["y"])
            # Проверяем близость к голове врага
            dist = abs(next_pos[0] - enemy_head[0]) + abs(next_pos[1] - enemy_head[1])
            if dist == 1:
                score += 5.0
            elif dist == 2:
                score += 2.0
    
    return score

# ============================================================================
# БЕЗОПАСНЫЙ FALLBACK
# ============================================================================

def choose_move_safe(game_state: Dict) -> str:
    """Максимально быстрый безопасный выбор хода."""
    legal = get_legal_moves_fast(game_state)
    if legal:
        return legal[0]
    return "up"

# ============================================================================
# ПРОФИЛИРОВАНИЕ ДЛЯ ОТЛАДКИ
# ============================================================================

class Timer:
    """Таймер для профилирования."""
    
    def __init__(self):
        self.start_time = None
        self.elapsed = 0
    
    def start(self):
        self.start_time = time.perf_counter()
    
    def stop(self):
        if self.start_time:
            self.elapsed = time.perf_counter() - self.start_time
            self.start_time = None
        return self.elapsed

# Для отладки можно раскомментировать:
# _timer = Timer()

def choose_move_with_profile(game_state: Dict) -> str:
    """Версия с профилированием для отладки."""
    # _timer.start()
    result = choose_move(game_state)
    # elapsed = _timer.stop()
    # if elapsed > MAX_RESPONSE_TIME:
    #     print(f"WARNING: Move took {elapsed:.3f}s")
    return result