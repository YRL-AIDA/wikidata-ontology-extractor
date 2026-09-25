"""
Построение чистой онтологической схемы предметных классов Wikidata
из экспорта zelph (файл hierarchy_export.txt).

Что делает:
  1. Загружает рёбра подклассовости (child → parent)
  2. Исключает метаклассы (транзитивно от корневых)
  3. Исключает системные сущности (категории, страницы значений и т.д.)
  4. Строит транзитивное замыкание (все предки каждого класса)
  5. Сохраняет чистую схему в JSON

Использование:
  pip install tqdm
  python extract_class_schema.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    print("Установите:  pip install tqdm")
    sys.exit(1)


# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

INPUT_FILE = "hierarchy_export.txt"
OUTPUT_FILE = "class_schema.json"

# Корневые метаклассы Викиданных (проверенные).
# Все их транзитивные подклассы будут исключены автоматически.
ROOT_METACLASSES = {
    "Q16889133",   # class (класс) — корневой метакласс
    "Q15138389",   # metaclass (метакласс)
    "Q19478619",   # Wikidata metaclass
    "Q21027609",   # Wikimedia metaclass
}

# Системные сущности, которые не являются предметными классами
SYSTEM_ENTITIES = {
    "Q4167410",    # Wikimedia category
    "Q19833835",   # Wikidata category
    "Q4167836",    # disambiguation page
    "Q1751888",    # Wikipedia disambiguation page
    "Q1561876",    # Wikimedia list article
    "Q13406463",   # Wikimedia list
    "Q11266439",   # Wikimedia template
    "Q19887878",   # Wikimedia navigation template
    "Q4663903",    # project page
    "Q21286738",   # human name disambiguation
}

# Все исключённые идентификаторы
EXCLUDED_ROOTS = ROOT_METACLASSES | SYSTEM_ENTITIES


# ============================================================
# ЗАГРУЗКА РЁБЕР
# ============================================================

def load_edges(path: str) -> list:
    """
    Загружает рёбра из TSV-файла.
    Формат: child<tab>parent
    """
    edges = []
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in tqdm(f, desc="Чтение рёбер", ncols=100):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            child = parts[0].strip("<>").split("/")[-1]
            parent = parts[1].strip("<>").split("/")[-1]
            if child and parent and child.startswith("Q") and parent.startswith("Q"):
                edges.append((child, parent))

    print(f"Загружено рёбер: {len(edges):,}")
    return edges


# ============================================================
# ПОСТРОЕНИЕ ГРАФА
# ============================================================

def build_graph(edges: list) -> tuple:
    """
    Строит направленный граф child → parent и parent → child.
    """
    child_to_parents = defaultdict(set)
    parent_to_children = defaultdict(set)
    all_classes = set()

    for child, parent in edges:
        child_to_parents[child].add(parent)
        parent_to_children[parent].add(child)
        all_classes.add(child)
        all_classes.add(parent)

    return child_to_parents, parent_to_children, all_classes


# ============================================================
# ФИЛЬТРАЦИЯ МЕТАКЛАССОВ
# ============================================================

def find_metaclasses(parent_to_children: dict, all_classes: set) -> set:
    """
    Находит все классы, которые транзитивно являются подклассами
    корневых метаклассов. Это и есть множество всех метаклассов.
    """
    metaclasses = set()
    stack = list(ROOT_METACLASSES & all_classes)

    while stack:
        current = stack.pop()
        if current in metaclasses:
            continue
        metaclasses.add(current)
        # Все подклассы метакласса тоже метаклассы
        stack.extend(parent_to_children.get(current, set()))

    return metaclasses


def filter_schema(edges: list, metaclasses: set) -> list:
    """
    Удаляет из схемы рёбра, в которых участвует хотя бы один метакласс
    или системная сущность.
    """
    clean_edges = []
    edges_set = set()

    for child, parent in edges:
        if child in metaclasses or parent in metaclasses:
            continue
        if child in SYSTEM_ENTITIES or parent in SYSTEM_ENTITIES:
            continue
        if child == parent:
            continue
        key = (child, parent)
        if key in edges_set:
            continue
        edges_set.add(key)
        clean_edges.append({"child": child, "parent": parent})

    return clean_edges


# ============================================================
# ТРАНЗИТИВНОЕ ЗАМЫКАНИЕ
# ============================================================

def build_transitive_closure(clean_edges: list) -> dict:
    """
    Для каждого класса вычисляет всех его предков (транзитивно).
    """
    child_to_parents = defaultdict(list)
    for e in clean_edges:
        child_to_parents[e["child"]].append(e["parent"])

    all_classes = set(e["child"] for e in clean_edges) | set(e["parent"] for e in clean_edges)
    ancestors = {}

    for class_id in tqdm(sorted(all_classes), desc="Транзитивное замыкание", ncols=100):
        result = set()
        stack = list(child_to_parents.get(class_id, []))
        visited = {class_id}
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            result.add(cur)
            stack.extend(child_to_parents.get(cur, []))
        ancestors[class_id] = sorted(result)

    return ancestors


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    print("=" * 70)
    print("Построение чистой онтологической схемы предметных классов")
    print("=" * 70)

    # 1. Загрузка
    print("\n[1/5] Загрузка рёбер...")
    edges = load_edges(INPUT_FILE)
    print(f"      Всего рёбер: {len(edges):,}")

    # 2. Построение графа
    print("\n[2/5] Построение графа...")
    child_to_parents, parent_to_children, all_classes = build_graph(edges)
    print(f"      Классов в графе: {len(all_classes):,}")

    # 3. Поиск метаклассов
    print("\n[3/5] Поиск метаклассов...")
    metaclasses = find_metaclasses(parent_to_children, all_classes)
    print(f"      Метаклассов найдено: {len(metaclasses):,}")

    # 4. Фильтрация
    print("\n[4/5] Фильтрация схемы...")
    clean_edges = filter_schema(edges, metaclasses)
    clean_classes = set(e["child"] for e in clean_edges) | set(e["parent"] for e in clean_edges)
    clean_children = set(e["child"] for e in clean_edges)
    clean_parents = set(e["parent"] for e in clean_edges)

    print(f"      Предметных классов: {len(clean_classes):,}")
    print(f"      Рёбер в схеме:      {len(clean_edges):,}")
    print(f"      Корневых классов:   {len(clean_parents - clean_children):,}")
    print(f"      Листовых классов:   {len(clean_children - clean_parents):,}")

    # 5. Транзитивное замыкание и сохранение
    print("\n[5/5] Транзитивное замыкание и сохранение...")
    ancestors = build_transitive_closure(clean_edges)

    schema = {
        "edges": clean_edges,
        "all_ancestors": ancestors,
        "stats": {
            "total_classes": len(clean_classes),
            "total_edges": len(clean_edges),
            "root_classes": len(clean_parents - clean_children),
            "leaf_classes": len(clean_children - clean_parents),
            "metaclasses_removed": len(metaclasses),
        },
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    size_mb = Path(OUTPUT_FILE).stat().st_size / (1024 * 1024)
    print(f"\n{'='*70}")
    print(f"✅ ГОТОВО!")
    print(f"{'='*70}")
    print(f"Файл:           {OUTPUT_FILE}")
    print(f"Размер:         {size_mb:.1f} МБ")
    print(f"Классов:        {schema['stats']['total_classes']:,}")
    print(f"Связей:         {schema['stats']['total_edges']:,}")
    print(f"Метаклассов:    {schema['stats']['metaclasses_removed']:,} (исключено)")
    print(f"\nСтруктура файла:")
    print(f"  edges:          list of {{child, parent}}")
    print(f"  all_ancestors:  dict class_id -> list of all ancestors")
    print(f"  stats:          статистика схемы")


if __name__ == "__main__":
    main()
