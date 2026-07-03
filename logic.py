# logic_enhanced.py
"""Enhanced heuristic logic for maximum survival in Battlesnake.

Key improvements:
1. Multi-turn planning with lookahead
2. Space control and territory management
3. Intelligent food seeking with risk assessment
4. Head-to-head combat tactics
5. Adaptable strategy based on game phase
"""

from collections import deque
from typing import Dict, List, Optional, Set, Tuple
import random
import math

Point = Tuple[int, int]

DIRECTIONS: Dict[str, Point] = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}

# --- Конфигурация стратегии ---
class StrategyConfig:
    # Приоритеты в разных фазах игры
    EARLY_GAME_TURNS = 20  # начальная фаза
    MID_GAME_TURNS = 80    # средняя фаза
    
    # Пороги здоровья
    CRITICAL_HEALTH = 25   # критический уровень - срочно искать еду
    LOW_HEALTH = 50        # низкий уровень - активно искать еду
    GOOD_HEALTH = 80       # хороший уровень - можно играть агрессивно
    
    # Веса для разных стратегий
    SURVIVAL_WEIGHT = 3.0  # вес выживания
    FOOD_WEIGHT = 2.0      # вес поиска еды
    AGGRESSIVE_WEIGHT = 1.5  # вес агрессивных действий
    TERRITORY_WEIGHT = 1.0  # вес захвата территории
    
    # Размер окна для планирования
    PLANNING_HORIZON = 3   # на сколько ходов вперед смотреть

def get_info() -> Dict[str, str]:
    """Appearance + metadata returned from GET /."""
    return {
        "apiversion": "1",
        "author": "hackathon",
        "color": "#6434eb",
        "head": "smart-caterpillar",
        "tail": "weight",
        "version": "2.0.0",
    }

# ============================================================================
# ОСНОВНАЯ ЛОГИКА ВЫБОРА ХОДА
# ============================================================================

def choose_move(game_state: Dict) -> str:
    """Enhanced move selection with multi-strategy approach."""
    try:
        # Анализируем текущую ситуацию
        context = analyze_game_context(game_state)
        
        # Получаем все возможные ходы с оценками
        moves_scores = evaluate_all_moves(game_state, context)
        
        # Выбираем лучший ход
        if moves_scores:
            best_move = max(moves_scores, key=lambda x: x[1])[0]
            return best_move
        
        # Если нет безопасных ходов - пробуем любой доступный
        legal = get_legal_moves(game_state)
        return legal[0] if legal else "up"
        
    except Exception as e:
        # В случае ошибки используем базовую эвристику
        return choose_move_heuristic_safe(game_state)

# ============================================================================
# АНАЛИЗ КОНТЕКСТА ИГРЫ
# ============================================================================

def analyze_game_context(game_state: Dict) -> Dict:
    """Анализирует текущую игровую ситуацию."""
    you = game_state["you"]
    board = game_state["board"]
    snakes = board["snakes"]
    
    context = {
        "phase": determine_game_phase(game_state),
        "health_status": get_health_status(you["health"]),
        "space_advantage": calculate_space_advantage(game_state),
        "size_advantage": calculate_size_advantage(game_state),
        "enemy_count": len(snakes) - 1,
        "food_abundance": len(board["food"]),
        "aggressive_opponents": detect_aggressive_opponents(game_state),
        "choke_points": find_choke_points(game_state),
    }
    
    # Определяем основную стратегию
    context["primary_strategy"] = determine_primary_strategy(context, game_state)
    
    return context

def determine_game_phase(game_state: Dict) -> str:
    """Определяет фазу игры."""
    turn = game_state["turn"]
    total_snakes = len(game_state["board"]["snakes"])
    
    if turn < StrategyConfig.EARLY_GAME_TURNS:
        return "early"
    elif turn < StrategyConfig.MID_GAME_TURNS:
        if total_snakes > 3:
            return "mid_many"
        else:
            return "mid_few"
    else:
        if total_snakes > 2:
            return "late_many"
        else:
            return "late_duel"

def get_health_status(health: int) -> str:
    """Определяет статус здоровья."""
    if health < StrategyConfig.CRITICAL_HEALTH:
        return "critical"
    elif health < StrategyConfig.LOW_HEALTH:
        return "low"
    elif health < StrategyConfig.GOOD_HEALTH:
        return "moderate"
    else:
        return "good"

def calculate_space_advantage(game_state: Dict) -> float:
    """Рассчитывает преимущество в контроле пространства."""
    you = game_state["you"]
    head = (you["head"]["x"], you["head"]["y"])
    board = game_state["board"]
    occupied = get_occupied_cells(game_state)
    
    # Подсчет доступного пространства для нашей змейки
    my_space = flood_fill(head, occupied, board["width"], board["height"])
    
    # Подсчет пространства для врагов
    enemy_spaces = []
    for snake in board["snakes"]:
        if snake["id"] == you["id"]:
            continue
        enemy_head = (snake["head"]["x"], snake["head"]["y"])
        enemy_space = flood_fill(enemy_head, occupied, board["width"], board["height"])
        enemy_spaces.append(enemy_space)
    
    if not enemy_spaces:
        return 1.0
    
    avg_enemy_space = sum(enemy_spaces) / len(enemy_spaces)
    if avg_enemy_space == 0:
        return 1.0 if my_space > 0 else 0.0
    
    return min(my_space / avg_enemy_space, 3.0)

def calculate_size_advantage(game_state: Dict) -> float:
    """Рассчитывает преимущество в размере."""
    you = game_state["you"]
    my_length = you["length"]
    
    max_enemy_length = 0
    for snake in game_state["board"]["snakes"]:
        if snake["id"] != you["id"]:
            max_enemy_length = max(max_enemy_length, snake["length"])
    
    if max_enemy_length == 0:
        return 1.0
    
    return my_length / max_enemy_length

def detect_aggressive_opponents(game_state: Dict) -> int:
    """Определяет количество агрессивных противников."""
    you = game_state["you"]
    head = (you["head"]["x"], you["head"]["y"])
    aggressive = 0
    
    for snake in game_state["board"]["snakes"]:
        if snake["id"] == you["id"]:
            continue
        enemy_head = (snake["head"]["x"], snake["head"]["y"])
        
        # Проверяем, движется ли враг в нашу сторону
        if abs(head[0] - enemy_head[0]) + abs(head[1] - enemy_head[1]) <= 4:
            # Проверяем, больше ли он или равен нам
            if snake["length"] >= you["length"]:
                aggressive += 1
    
    return aggressive

def find_choke_points(game_state: Dict) -> Set[Point]:
    """Находит узкие места на карте."""
    board = game_state["board"]
    width, height = board["width"], board["height"]
    occupied = get_occupied_cells(game_state)
    choke_points = set()
    
    for x in range(width):
        for y in range(height):
            point = (x, y)
            if point in occupied:
                continue
            
            # Проверяем, сколько свободных соседей
            free_neighbors = 0
            for dx, dy in DIRECTIONS.values():
                nx, ny = x + dx, y + dy
                if (0 <= nx < width and 0 <= ny < height and 
                    (nx, ny) not in occupied):
                    free_neighbors += 1
            
            # Узкое место - точка с 1-2 свободными соседями
            if 1 <= free_neighbors <= 2:
                choke_points.add(point)
    
    return choke_points

def determine_primary_strategy(context: Dict, game_state: Dict) -> str:
    """Определяет основную стратегию на основе контекста."""
    health_status = context["health_status"]
    phase = context["phase"]
    
    # Критическое здоровье - срочно искать еду
    if health_status == "critical":
        return "desperate_food"
    
    # Начало игры - исследование
    if phase == "early":
        return "explore"
    
    # Низкое здоровье - активный поиск еды
    if health_status == "low":
        return "seek_food"
    
    # Если мы больше всех и здоровы - агрессивная игра
    if (context["size_advantage"] > 1.2 and 
        context["space_advantage"] > 1.0 and
        health_status == "good"):
        return "aggressive"
    
    # Поздняя игра с малым количеством змей
    if phase in ["late_duel", "late_many"]:
        if context["size_advantage"] > 1.0:
            return "defensive_control"
        else:
            return "survival"
    
    # Стандартная стратегия - баланс
    return "balanced"

# ============================================================================
# ОЦЕНКА ХОДОВ
# ============================================================================

def evaluate_all_moves(game_state: Dict, context: Dict) -> List[Tuple[str, float]]:
    """Оценивает все возможные ходы с учетом контекста."""
    legal_moves = get_legal_moves(game_state)
    if not legal_moves:
        return []
    
    move_scores = []
    for move in legal_moves:
        score = evaluate_move(game_state, move, context)
        move_scores.append((move, score))
    
    # Добавляем немного случайности для разнообразия
    max_score = max(s[1] for s in move_scores) if move_scores else 1
    move_scores = [(m, s + random.uniform(0, 0.01 * max_score)) 
                   for m, s in move_scores]
    
    return move_scores

def evaluate_move(game_state: Dict, move: str, context: Dict) -> float:
    """Оценивает конкретный ход с учетом всех факторов."""
    board = game_state["board"]
    you = game_state["you"]
    width, height = board["width"], board["height"]
    head = (you["head"]["x"], you["head"]["y"])
    dx, dy = DIRECTIONS[move]
    next_pos = (head[0] + dx, head[1] + dy)
    
    occupied = get_occupied_cells(game_state)
    danger_zones = get_danger_zones(game_state)
    
    # Базовые проверки безопасности
    if not is_safe_cell(next_pos, game_state):
        return -float('inf')
    
    score = 0.0
    
    # 1. ФАКТОР ВЫЖИВАНИЯ (наивысший приоритет)
    survival_score = calculate_survival_score(game_state, move)
    score += survival_score * StrategyConfig.SURVIVAL_WEIGHT
    
    # 2. ФАКТОР ЕДЫ
    food_score = calculate_food_score(game_state, move, context)
    score += food_score * StrategyConfig.FOOD_WEIGHT
    
    # 3. АГРЕССИВНЫЙ ФАКТОР
    if context["primary_strategy"] in ["aggressive", "defensive_control"]:
        aggressive_score = calculate_aggressive_score(game_state, move)
        score += aggressive_score * StrategyConfig.AGGRESSIVE_WEIGHT
    
    # 4. КОНТРОЛЬ ТЕРРИТОРИИ
    territory_score = calculate_territory_score(game_state, move, context)
    score += territory_score * StrategyConfig.TERRITORY_WEIGHT
    
    # 5. ПЛАНИРОВАНИЕ НА НЕСКОЛЬКО ХОДОВ ВПЕРЕД
    if context["health_status"] not in ["critical", "low"]:
        lookahead_score = calculate_lookahead_score(game_state, move, context)
        score += lookahead_score * 0.5
    
    # 6. АДАПТИВНЫЕ ШТРАФЫ И БОНУСЫ
    score += calculate_adaptive_bonuses(game_state, move, context)
    
    return score

# ============================================================================
# РАСЧЕТ ОТДЕЛЬНЫХ ФАКТОРОВ
# ============================================================================

def calculate_survival_score(game_state: Dict, move: str) -> float:
    """Рассчитывает оценку выживания для хода."""
    board = game_state["board"]
    you = game_state["you"]
    width, height = board["width"], board["height"]
    head = (you["head"]["x"], you["head"]["y"])
    dx, dy = DIRECTIONS[move]
    next_pos = (head[0] + dx, head[1] + dy)
    
    occupied = get_occupied_cells(game_state)
    danger_zones = get_danger_zones(game_state)
    
    score = 0.0
    
    # Базовое пространство для маневра
    space = flood_fill(next_pos, occupied, width, height)
    space_ratio = space / (width * height)
    score += space_ratio * 10.0
    
    # Избегание опасных зон
    if next_pos in danger_zones:
        score -= 20.0
    
    # Проверка на ловушку
    if is_dead_end(next_pos, occupied, width, height):
        score -= 30.0
    
    # Проверка head-to-head
    head_to_head_score = evaluate_head_to_head(game_state, move)
    score += head_to_head_score
    
    # Оценка возможности escape
    escape_score = evaluate_escape_options(next_pos, game_state)
    score += escape_score
    
    return score

def calculate_food_score(game_state: Dict, move: str, context: Dict) -> float:
    """Рассчитывает оценку поиска еды."""
    board = game_state["board"]
    you = game_state["you"]
    head = (you["head"]["x"], you["head"]["y"])
    dx, dy = DIRECTIONS[move]
    next_pos = (head[0] + dx, head[1] + dy)
    health = you["health"]
    foods = [(f["x"], f["y"]) for f in board["food"]]
    
    if not foods:
        return 0.0
    
    score = 0.0
    
    # Срочность поиска еды в зависимости от здоровья
    urgency = 1.0
    if health < StrategyConfig.CRITICAL_HEALTH:
        urgency = 3.0
    elif health < StrategyConfig.LOW_HEALTH:
        urgency = 2.0
    
    # Находим ближайшую еду
    nearest_food_dist = min(abs(next_pos[0] - f[0]) + abs(next_pos[1] - f[1]) 
                           for f in foods)
    current_dist = min(abs(head[0] - f[0]) + abs(head[1] - f[1]) 
                      for f in foods)
    
    # Бонус за приближение к еде
    dist_improvement = current_dist - nearest_food_dist
    score += dist_improvement * urgency
    
    # Бонус, если ход ведет на клетку с едой
    if next_pos in foods:
        score += 15.0 * urgency
    
    # Избегаем опасной еды (около врагов)
    for food in foods:
        if is_food_dangerous(food, game_state):
            if next_pos == food:
                score -= 10.0
    
    return score

def calculate_aggressive_score(game_state: Dict, move: str) -> float:
    """Рассчитывает агрессивную оценку хода."""
    you = game_state["you"]
    board = game_state["board"]
    head = (you["head"]["x"], you["head"]["y"])
    dx, dy = DIRECTIONS[move]
    next_pos = (head[0] + dx, head[1] + dy)
    
    score = 0.0
    
    for snake in board["snakes"]:
        if snake["id"] == you["id"]:
            continue
        
        enemy_head = (snake["head"]["x"], snake["head"]["y"])
        dist = abs(next_pos[0] - enemy_head[0]) + abs(next_pos[1] - enemy_head[1])
        
        # Если мы можем съесть голову врага
        if dist == 1 and snake["length"] <= you["length"]:
            score += 25.0
        
        # Если мы можем отрезать врага
        if dist == 2 and snake["length"] <= you["length"]:
            # Проверяем, можем ли мы занять клетку перед ним
            for ddx, ddy in DIRECTIONS.values():
                block_pos = (enemy_head[0] + ddx, enemy_head[1] + ddy)
                if block_pos == next_pos:
                    score += 10.0
    
    return score

def calculate_territory_score(game_state: Dict, move: str, context: Dict) -> float:
    """Рассчитывает оценку контроля территории."""
    board = game_state["board"]
    you = game_state["you"]
    head = (you["head"]["x"], you["head"]["y"])
    dx, dy = DIRECTIONS[move]
    next_pos = (head[0] + dx, head[1] + dy)
    width, height = board["width"], board["height"]
    
    occupied = get_occupied_cells(game_state)
    score = 0.0
    
    # Контроль центра карты
    center = ((width - 1) / 2, (height - 1) / 2)
    dist_to_center = abs(next_pos[0] - center[0]) + abs(next_pos[1] - center[1])
    score += (width + height - dist_to_center) / 2
    
    # Контроль пространства (Voronoi)
    voronoi_score = calculate_voronoi_control(next_pos, game_state)
    score += voronoi_score * 2.0
    
    # Избегаем углов (кроме критических ситуаций)
    if context["health_status"] not in ["critical", "low"]:
        if is_corner(next_pos, width, height):
            score -= 5.0
    
    return score

def calculate_lookahead_score(game_state: Dict, move: str, context: Dict) -> float:
    """Рассчитывает оценку с учетом планирования на несколько ходов."""
    board = game_state["board"]
    you = game_state["you"]
    head = (you["head"]["x"], you["head"]["y"])
    dx, dy = DIRECTIONS[move]
    next_pos = (head[0] + dx, head[1] + dy)
    
    score = 0.0
    
    # Симулируем следующие ходы
    for depth in range(1, StrategyConfig.PLANNING_HORIZON + 1):
        # Проверяем, не попадет ли змейка в ловушку через depth ходов
        future_safety = simulate_future_safety(next_pos, game_state, depth)
        score += future_safety * (1.0 / depth)
    
    return score

def calculate_adaptive_bonuses(game_state: Dict, move: str, context: Dict) -> float:
    """Рассчитывает адаптивные бонусы и штрафы."""
    you = game_state["you"]
    board = game_state["board"]
    head = (you["head"]["x"], you["head"]["y"])
    dx, dy = DIRECTIONS[move]
    next_pos = (head[0] + dx, head[1] + dy)
    
    score = 0.0
    
    # Бонус за сохранение пространства для маневра
    if context["space_advantage"] > 1.2:
        # Если у нас преимущество - агрессивнее
        if is_advancing(next_pos, game_state):
            score += 2.0
    else:
        # Если мы в меньшинстве - защита
        if is_retreating(next_pos, game_state):
            score += 3.0
    
    # Адаптация к агрессивным противникам
    if context["aggressive_opponents"] > 0:
        # Держим дистанцию от агрессивных врагов
        dist_to_aggressive = min_distance_to_aggressive(next_pos, game_state)
        score += dist_to_aggressive * 0.5
    
    return score

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def get_occupied_cells(game_state: Dict) -> Set[Point]:
    """Возвращает все занятые клетки."""
    occupied = set()
    for snake in game_state["board"]["snakes"]:
        for seg in snake["body"]:
            occupied.add((seg["x"], seg["y"]))
    return occupied

def get_danger_zones(game_state: Dict) -> Set[Point]:
    """Возвращает опасные зоны (рядом с головами врагов)."""
    you = game_state["you"]
    danger = set()
    
    for snake in game_state["board"]["snakes"]:
        if snake["id"] == you["id"]:
            continue
        if snake["length"] >= you["length"]:
            head = (snake["head"]["x"], snake["head"]["y"])
            for dx, dy in DIRECTIONS.values():
                danger.add((head[0] + dx, head[1] + dy))
    
    return danger

def get_legal_moves(game_state: Dict) -> List[str]:
    """Возвращает список легальных ходов."""
    board = game_state["board"]
    you = game_state["you"]
    head = (you["head"]["x"], you["head"]["y"])
    width, height = board["width"], board["height"]
    occupied = get_occupied_cells(game_state)
    
    legal = []
    for move, (dx, dy) in DIRECTIONS.items():
        nx, ny = head[0] + dx, head[1] + dy
        if (0 <= nx < width and 0 <= ny < height and 
            (nx, ny) not in occupied):
            legal.append(move)
    
    return legal

def is_safe_cell(pos: Point, game_state: Dict) -> bool:
    """Проверяет, безопасна ли клетка."""
    board = game_state["board"]
    width, height = board["width"], board["height"]
    occupied = get_occupied_cells(game_state)
    danger = get_danger_zones(game_state)
    
    x, y = pos
    if not (0 <= x < width and 0 <= y < height):
        return False
    if pos in occupied:
        return False
    # Дополнительная проверка на отрезание пути
    if is_dead_end(pos, occupied, width, height):
        return False
    return True

def flood_fill(start: Point, occupied: Set[Point], width: int, height: int) -> int:
    """Подсчет достижимых клеток (BFS)."""
    if start in occupied:
        return 0
    
    seen = {start}
    stack = [start]
    count = 0
    limit = width * height
    
    while stack and count < limit:
        x, y = stack.pop()
        count += 1
        for dx, dy in DIRECTIONS.values():
            nx, ny = x + dx, y + dy
            nxt = (nx, ny)
            if (0 <= nx < width and 0 <= ny < height and 
                nxt not in seen and nxt not in occupied):
                seen.add(nxt)
                stack.append(nxt)
    
    return count

def is_dead_end(pos: Point, occupied: Set[Point], width: int, height: int) -> bool:
    """Проверяет, является ли клетка тупиком."""
    free_neighbors = 0
    for dx, dy in DIRECTIONS.values():
        nx, ny = pos[0] + dx, pos[1] + dy
        if (0 <= nx < width and 0 <= ny < height and 
            (nx, ny) not in occupied):
            free_neighbors += 1
    return free_neighbors == 1

def is_corner(pos: Point, width: int, height: int) -> bool:
    """Проверяет, находится ли клетка в углу."""
    x, y = pos
    corners = [(0, 0), (width-1, 0), (0, height-1), (width-1, height-1)]
    return pos in corners

def evaluate_head_to_head(game_state: Dict, move: str) -> float:
    """Оценивает head-to-head столкновения."""
    you = game_state["you"]
    head = (you["head"]["x"], you["head"]["y"])
    dx, dy = DIRECTIONS[move]
    next_pos = (head[0] + dx, head[1] + dy)
    
    for snake in game_state["board"]["snakes"]:
        if snake["id"] == you["id"]:
            continue
        enemy_head = (snake["head"]["x"], snake["head"]["y"])
        
        # Проверяем, не движется ли враг на нашу клетку
        for edx, edy in DIRECTIONS.values():
            enemy_next = (enemy_head[0] + edx, enemy_head[1] + edy)
            if enemy_next == next_pos:
                if snake["length"] >= you["length"]:
                    return -30.0  # проиграем или ничья
                else:
                    return 20.0   # победим
    
    return 0.0

def evaluate_escape_options(pos: Point, game_state: Dict) -> float:
    """Оценивает возможности побега с позиции."""
    board = game_state["board"]
    width, height = board["width"], board["height"]
    occupied = get_occupied_cells(game_state)
    
    escape_paths = 0
    for dx, dy in DIRECTIONS.values():
        nx, ny = pos[0] + dx, pos[1] + dy
        if (0 <= nx < width and 0 <= ny < height and 
            (nx, ny) not in occupied):
            # Проверяем, ведет ли путь к свободе
            sub_space = flood_fill((nx, ny), occupied, width, height)
            if sub_space > 10:  # достаточно пространства
                escape_paths += 1
    
    return escape_paths * 2.0

def calculate_voronoi_control(pos: Point, game_state: Dict) -> float:
    """Рассчитывает контроль пространства (Voronoi)."""
    you = game_state["you"]
    board = game_state["board"]
    width, height = board["width"], board["height"]
    occupied = get_occupied_cells(game_state)
    
    # Клетки, которые мы контролируем
    my_reachable = flood_fill(pos, occupied, width, height)
    
    # Клетки, которые контролируют враги
    enemy_reachable = 0
    for snake in board["snakes"]:
        if snake["id"] == you["id"]:
            continue
        enemy_head = (snake["head"]["x"], snake["head"]["y"])
        enemy_space = flood_fill(enemy_head, occupied, width, height)
        enemy_reachable += enemy_space
    
    if enemy_reachable == 0:
        return 1.0
    
    return my_reachable / (my_reachable + enemy_reachable)

def is_advancing(pos: Point, game_state: Dict) -> bool:
    """Проверяет, продвигается ли змейка к центру/врагам."""
    board = game_state["board"]
    width, height = board["width"], board["height"]
    center = ((width - 1) / 2, (height - 1) / 2)
    
    you = game_state["you"]
    head = (you["head"]["x"], you["head"]["y"])
    
    # Проверяем, приближаемся ли к центру
    current_dist = abs(head[0] - center[0]) + abs(head[1] - center[1])
    new_dist = abs(pos[0] - center[0]) + abs(pos[1] - center[1])
    
    return new_dist < current_dist

def is_retreating(pos: Point, game_state: Dict) -> bool:
    """Проверяет, отступает ли змейка."""
    board = game_state["board"]
    width, height = board["width"], board["height"]
    center = ((width - 1) / 2, (height - 1) / 2)
    
    you = game_state["you"]
    head = (you["head"]["x"], you["head"]["y"])
    
    current_dist = abs(head[0] - center[0]) + abs(head[1] - center[1])
    new_dist = abs(pos[0] - center[0]) + abs(pos[1] - center[1])
    
    return new_dist > current_dist

def is_food_dangerous(food: Point, game_state: Dict) -> bool:
    """Проверяет, находится ли еда в опасной зоне."""
    you = game_state["you"]
    
    for snake in game_state["board"]["snakes"]:
        if snake["id"] == you["id"]:
            continue
        if snake["length"] >= you["length"]:
            enemy_head = (snake["head"]["x"], snake["head"]["y"])
            dist = abs(food[0] - enemy_head[0]) + abs(food[1] - enemy_head[1])
            if dist <= 2:
                return True
    
    return False

def min_distance_to_aggressive(pos: Point, game_state: Dict) -> float:
    """Минимальное расстояние до агрессивных врагов."""
    you = game_state["you"]
    min_dist = float('inf')
    
    for snake in game_state["board"]["snakes"]:
        if snake["id"] == you["id"]:
            continue
        if snake["length"] >= you["length"]:
            enemy_head = (snake["head"]["x"], snake["head"]["y"])
            dist = abs(pos[0] - enemy_head[0]) + abs(pos[1] - enemy_head[1])
            min_dist = min(min_dist, dist)
    
    return min_dist if min_dist != float('inf') else 0

def simulate_future_safety(pos: Point, game_state: Dict, depth: int) -> float:
    """Симулирует безопасность через depth ходов."""
    board = game_state["board"]
    width, height = board["width"], board["height"]
    occupied = get_occupied_cells(game_state)
    
    # Простая симуляция: проверяем, сколько свободы останется
    # после продвижения вперед
    future_occupied = set(occupied)
    current_pos = pos
    
    for _ in range(depth):
        # Добавляем текущую позицию в занятые (как будто змейка движется)
        future_occupied.add(current_pos)
        
        # Проверяем доступное пространство
        space = flood_fill(current_pos, future_occupied, width, height)
        if space < 5:  # слишком мало места
            return 0.0
        
        # Ищем безопасное продолжение (упрощенно)
        best_next = None
        best_space = 0
        for dx, dy in DIRECTIONS.values():
            nx, ny = current_pos[0] + dx, current_pos[1] + dy
            nxt = (nx, ny)
            if (0 <= nx < width and 0 <= ny < height and 
                nxt not in future_occupied):
                sub_space = flood_fill(nxt, future_occupied, width, height)
                if sub_space > best_space:
                    best_space = sub_space
                    best_next = nxt
        
        if best_next is None:
            return 0.0
        
        current_pos = best_next
    
    return 1.0

# ============================================================================
# БЕЗОПАСНАЯ ЭВРИСТИКА (FALLBACK)
# ============================================================================

def choose_move_heuristic_safe(game_state: Dict) -> str:
    """Базовая эвристика для безопасного выбора хода."""
    board = game_state["board"]
    you = game_state["you"]
    width, height = board["width"], board["height"]
    head = (you["head"]["x"], you["head"]["y"])
    occupied = get_occupied_cells(game_state)
    danger = get_danger_zones(game_state)
    
    # Пробуем безопасные ходы
    safe_moves = []
    for move, (dx, dy) in DIRECTIONS.items():
        nx, ny = head[0] + dx, head[1] + dy
        pos = (nx, ny)
        if (0 <= nx < width and 0 <= ny < height and 
            pos not in occupied and pos not in danger):
            safe_moves.append(move)
    
    if safe_moves:
        return random.choice(safe_moves)
    
    # Если нет безопасных - пробуем любые легальные
    legal = get_legal_moves(game_state)
    if legal:
        return random.choice(legal)
    
    return "up"