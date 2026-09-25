"""
Проверка файла онтологической схемы классов (с лейблами И описаниями).
Показывает структуру, примеры данных и сохраняет небольшую выборку.
"""

import json
import random
import sys
from pathlib import Path

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

INPUT_FILE = "class_schema_with_labels_and_descriptions.json"
SAMPLE_FILE = "class_schema_sample.json"   # небольшая выборка для просмотра
SAMPLE_SIZE = 100                          # сколько классов сохранить в выборку


# ============================================================
# ФУНКЦИИ ПРОВЕРКИ
# ============================================================

def show_file_info(path: str) -> None:
    """Показывает базовую информацию о файле."""
    print("=" * 70)
    print("1. ИНФОРМАЦИЯ О ФАЙЛЕ")
    print("=" * 70)

    p = Path(path)
    if not p.exists():
        print(f"❌ Файл не найден: {path}")
        sys.exit(1)

    size_bytes = p.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    print(f"   Файл:      {path}")
    print(f"   Размер:    {size_mb:.1f} МБ ({size_bytes:,} байт)")
    print()


def show_raw_head(path: str, chars: int = 2000) -> None:
    """Показывает первые символы файла без полной загрузки."""
    print("=" * 70)
    print("2. ПЕРВЫЕ СИМВОЛЫ ФАЙЛА (сырой текст)")
    print("=" * 70)

    with open(path, "r", encoding="utf-8") as f:
        head = f.read(chars)

    print(head)
    print("\n   ... (продолжение следует)")
    print()


def load_and_inspect(path: str) -> dict:
    """Загружает файл и показывает структуру."""
    print("=" * 70)
    print("3. ЗАГРУЗКА И СТРУКТУРА ФАЙЛА")
    print("=" * 70)
    print("   Загрузка файла в память (может занять 30-60 сек)...")

    with open(path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    print(f"   ✅ Загружено успешно")
    print()
    print("   Ключи верхнего уровня:")
    for key in schema.keys():
        value = schema[key]
        if isinstance(value, list):
            print(f"      • {key}: list ({len(value):,} элементов)")
        elif isinstance(value, dict):
            print(f"      • {key}: dict ({len(value):,} ключей)")
        else:
            print(f"      • {key}: {type(value).__name__}")
    print()

    if "stats" in schema:
        print("   Статистика из файла:")
        for k, v in schema["stats"].items():
            print(f"      • {k}: {v:,}")
        print()

    return schema


def show_examples(schema: dict, count: int = 5) -> None:
    """Показывает примеры классов с лейблами И описаниями."""
    print("=" * 70)
    print(f"4. ПРИМЕРЫ КЛАССОВ С ОПИСАНИЯМИ ({count} штук)")
    print("=" * 70)

    class_info = schema.get("class_info", {})
    if not class_info:
        print("   ⚠ Поле 'class_info' отсутствует в схеме")
        return

    # Берём несколько известных классов
    known_ids = ["Q5", "Q515", "Q6256", "Q11424", "Q571",
                 "Q12136", "Q43229", "Q11173", "Q4830453", "Q619610"]

    shown = 0
    for qid in known_ids:
        if qid in class_info and shown < count:
            info = class_info[qid]
            ancestors = schema.get("all_ancestors", {}).get(qid, [])

            print(f"\n   {qid}:")
            print(f"      Название (EN):  {info.get('label_en', '—') or '—'}")
            print(f"      Название (RU):  {info.get('label_ru', '—') or '—'}")
            print(f"      Описание (EN):  {info.get('description_en', '—') or '—'}")
            print(f"      Описание (RU):  {info.get('description_ru', '—') or '—'}")
            print(f"      Предков:        {len(ancestors)}")
            if ancestors:
                print(f"      Первые 5:       {ancestors[:5]}")
            shown += 1

    # Если известных классов не хватило, показываем случайные
    if shown < count:
        remaining = [q for q in class_info if q not in known_ids]
        random.seed(42)
        for qid in random.sample(remaining, min(count - shown, len(remaining))):
            info = class_info[qid]
            ancestors = schema.get("all_ancestors", {}).get(qid, [])

            print(f"\n   {qid}:")
            print(f"      Название (EN):  {info.get('label_en', '—') or '—'}")
            print(f"      Название (RU):  {info.get('label_ru', '—') or '—'}")
            print(f"      Описание (EN):  {info.get('description_en', '—') or '—'}")
            print(f"      Описание (RU):  {info.get('description_ru', '—') or '—'}")
            print(f"      Предков:        {len(ancestors)}")
            shown += 1

    print()


def show_label_statistics(schema: dict) -> None:
    """Показывает статистику по названиям И описаниям."""
    print("=" * 70)
    print("5. СТАТИСТИКА НАЗВАНИЙ И ОПИСАНИЙ")
    print("=" * 70)

    class_info = schema.get("class_info", {})
    total = len(class_info)

    if total == 0:
        print("   ⚠ class_info пуст")
        return

    # Названия
    en_labels = sum(1 for v in class_info.values() if v.get("label_en"))
    ru_labels = sum(1 for v in class_info.values() if v.get("label_ru"))

    # Описания
    en_descs = sum(1 for v in class_info.values() if v.get("description_en"))
    ru_descs = sum(1 for v in class_info.values() if v.get("description_ru"))

    # Комбинированная статистика
    full_info = sum(1 for v in class_info.values()
                    if v.get("label_en") and v.get("label_ru")
                    and v.get("description_en") and v.get("description_ru"))
    no_info = sum(1 for v in class_info.values()
                  if not v.get("label_en") and not v.get("label_ru"))

    print(f"   Всего классов:              {total:,}")
    print()
    print(f"   НАЗВАНИЯ:")
    print(f"      С английским:            {en_labels:,} ({en_labels/total*100:.1f}%)")
    print(f"      С русским:               {ru_labels:,} ({ru_labels/total*100:.1f}%)")
    print()
    print(f"   ОПИСАНИЯ:")
    print(f"      С английским:            {en_descs:,} ({en_descs/total*100:.1f}%)")
    print(f"      С русским:               {ru_descs:,} ({ru_descs/total*100:.1f}%)")
    print()
    print(f"   С полными данными (все 4 поля):  {full_info:,} ({full_info/total*100:.1f}%)")
    print(f"   Без каких-либо названий:         {no_info:,} ({no_info/total*100:.1f}%)")
    print()


def save_sample(schema: dict, sample_path: str, sample_size: int = 100) -> None:
    """Сохраняет небольшую выборку в отдельный файл (с описаниями)."""
    print("=" * 70)
    print(f"6. СОХРАНЕНИЕ ВЫБОРКИ ({sample_size} классов)")
    print("=" * 70)

    class_info = schema.get("class_info", {})
    edges = schema.get("edges", [])

    # Приоритет: известные классы + случайные
    known_ids = ["Q5", "Q515", "Q6256", "Q11424", "Q571",
                 "Q12136", "Q43229", "Q11173", "Q4830453", "Q619610"]
    selected = [q for q in known_ids if q in class_info]

    remaining = [q for q in class_info if q not in selected]
    random.seed(42)
    selected += random.sample(remaining, min(sample_size - len(selected), len(remaining)))

    # Формируем выборку
    sample_edges = [e for e in edges if e["child"] in selected or e["parent"] in selected]
    sample_ancestors = {q: schema["all_ancestors"].get(q, []) for q in selected}
    sample_info = {q: class_info[q] for q in selected}

    sample = {
        "description": f"Выборка {len(selected)} классов из полной схемы (с описаниями)",
        "class_info": sample_info,
        "all_ancestors": sample_ancestors,
        "edges": sample_edges[:200],
        "stats": {
            "total_classes_in_sample": len(selected),
            "total_edges_in_sample": len(sample_edges[:200]),
        }
    }

    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    size_kb = Path(sample_path).stat().st_size / 1024
    print(f"   ✅ Сохранено: {sample_path}")
    print(f"   Размер выборки: {size_kb:.1f} КБ")
    print(f"   Этот файл можно открыть в любом текстовом редакторе")
    print()


def validate_integrity(schema: dict) -> None:
    """Проверяет целостность схемы."""
    print("=" * 70)
    print("7. ПРОВЕРКА ЦЕЛОСТНОСТИ")
    print("=" * 70)

    edges = schema.get("edges", [])
    class_info = schema.get("class_info", {})
    all_ancestors = schema.get("all_ancestors", {})

    errors = []

    # Проверка 1: все классы из рёбер есть в class_info
    edge_classes = set()
    for e in edges:
        edge_classes.add(e["child"])
        edge_classes.add(e["parent"])

    missing_info = edge_classes - set(class_info.keys())
    if missing_info:
        errors.append(f"Классов в рёбрах без информации: {len(missing_info):,}")
    else:
        print(f"   ✅ Все классы из рёбер имеют информацию")

    # Проверка 2: все классы из class_info есть в all_ancestors
    missing_anc = set(class_info.keys()) - set(all_ancestors.keys())
    if missing_anc:
        errors.append(f"Классов без данных о предках: {len(missing_anc):,}")
    else:
        print(f"   ✅ Все классы имеют данные о предках")

    # Проверка 3: нет само-ссылок в рёбрах
    self_refs = [e for e in edges if e["child"] == e["parent"]]
    if self_refs:
        errors.append(f"Само-ссылок в рёбрах: {len(self_refs):,}")
    else:
        print(f"   ✅ Само-ссылок нет")

    # Проверка 4: нет дубликатов рёбер
    edge_set = set()
    duplicates = 0
    for e in edges:
        key = (e["child"], e["parent"])
        if key in edge_set:
            duplicates += 1
        edge_set.add(key)
    if duplicates:
        errors.append(f"Дубликатов рёбер: {duplicates:,}")
    else:
        print(f"   ✅ Дубликатов рёбер нет")

    # Проверка 5: метаклассы не присутствуют
    meta_ids = {"Q16889133", "Q15138389", "Q19478619"}
    found_meta = meta_ids & set(class_info.keys())
    if found_meta:
        errors.append(f"Найдены метаклассы: {found_meta}")
    else:
        print(f"   ✅ Метаклассы исключены")

    # Проверка 6: наличие полей описаний в структуре
    if class_info:
        sample_class = next(iter(class_info.values()))
        required_fields = ["label_en", "label_ru", "description_en", "description_ru"]
        missing_fields = [f for f in required_fields if f not in sample_class]
        if missing_fields:
            errors.append(f"Отсутствуют поля в структуре: {missing_fields}")
        else:
            print(f"   ✅ Структура содержит все поля (лейблы + описания)")

    print()
    if errors:
        print("   ⚠ НАЙДЕНЫ ПРОБЛЕМЫ:")
        for err in errors:
            print(f"      • {err}")
    else:
        print("   ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")
    print()


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    print("\n" + "=" * 70)
    print("ПРОВЕРКА ФАЙЛА ОНТОЛОГИЧЕСКОЙ СХЕМЫ (с описаниями)")
    print("=" * 70 + "\n")

    # Шаг 1: информация о файле
    show_file_info(INPUT_FILE)

    # Шаг 2: первые символы (быстро, без загрузки)
    show_raw_head(INPUT_FILE, chars=1500)

    # Шаг 3: полная загрузка
    schema = load_and_inspect(INPUT_FILE)

    # Шаг 4: примеры классов с описаниями
    show_examples(schema, count=5)

    # Шаг 5: статистика названий и описаний
    show_label_statistics(schema)

    # Шаг 6: сохранение выборки
    save_sample(schema, SAMPLE_FILE, SAMPLE_SIZE)

    # Шаг 7: проверка целостности
    validate_integrity(schema)

    print("=" * 70)
    print("ПРОВЕРКА ЗАВЕРШЕНА")
    print("=" * 70)
    print(f"\nДля просмотра откройте файл: {SAMPLE_FILE}")
    print("Он небольшой и откроется в любом редакторе.")


if __name__ == "__main__":
    main()
