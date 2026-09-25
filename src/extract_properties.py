"""
Извлечение полной онтологической схемы свойств Wikidata.
Финальная версия: корректные запросы + кэширование прогресса.

Что собирает:
  1. Все свойства с типами данных
  2. Иерархию свойств (subproperty of, P1647)
  3. Ограничения типа (domain)
  4. Ограничения типа значения (range)
  5. Обратные свойства (P1696)
  6. Названия и описания на английском и русском

Использование:
  pip install SPARQLWrapper requests tqdm
  python extract_properties.py
"""

import json
import time
import pickle
import requests
from pathlib import Path
from collections import defaultdict

try:
    from SPARQLWrapper import SPARQLWrapper, JSON, SPARQLExceptions
except ImportError:
    print("Установите:  pip install SPARQLWrapper")
    raise

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

ENDPOINT = "https://query.wikidata.org/sparql"
API_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "PropertySchemaExtractor/FINAL (semantic-table-interpretation)"
OUTPUT_FILE = "properties_schema_with_labels.json"
CACHE_FILE = "properties_cache.pkl"

# Агрессивные настройки для rate limiting
RETRIES = 6
BASE_DELAY = 70          # базовая задержка между SPARQL-запросами
REQUEST_DELAY = 70       # задержка между шагами
LABEL_BATCH_SIZE = 50
LABEL_DELAY = 3          # задержка между батчами лейблов
LABEL_RETRIES = 4


# ============================================================
# КЭШИРОВАНИЕ ПРОГРЕССА
# ============================================================

def load_cache() -> dict:
    """Загружает прогресс из кэша."""
    p = Path(CACHE_FILE)
    if p.exists():
        try:
            with open(p, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"⚠ Не удалось загрузить кэш: {e}")
    return {
        "properties": None,
        "steps_completed": set(),
        "labels_fetched": set(),  # множество ID с полученными лейблами
    }


def save_cache(cache: dict) -> None:
    """Сохраняет прогресс на диск."""
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(cache, f)


# ============================================================
# ВЫПОЛНЕНИЕ SPARQL С АГРЕССИВНЫМИ РЕТРАЯМИ
# ============================================================

def run_sparql(query: str, description: str = "", step_name: str = "") -> list:
    """
    Выполняет SPARQL-запрос с агрессивными ретраями для 429 ошибок.
    Возвращает список bindings, или None при невозможности выполнить.
    """
    if description:
        print(f"\n   === {description} ===")

    for attempt in range(1, RETRIES + 1):
        sparql = SPARQLWrapper(ENDPOINT)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        sparql.setTimeout(90)
        sparql.agent = USER_AGENT

        try:
            results = sparql.query().convert()
            bindings = results.get("results", {}).get("bindings", [])
            print(f"   ✓ Получено строк: {len(bindings):,}")

            if bindings:
                # Показываем пример первой строки
                print(f"   Пример:")
                for key, value in bindings[0].items():
                    val = str(value.get("value", ""))[:80]
                    print(f"      {key}: {val}")

            return bindings

        except SPARQLExceptions.QueryBadFormed as e:
            print(f"   ✗ Ошибка синтаксиса: {e}")
            return []

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate-limit" in err_str.lower():
                wait = BASE_DELAY * (attempt + 1)
                print(f"   ⚠ Rate limit (попытка {attempt}/{RETRIES})")
                print(f"      Ждём {wait} сек ({wait/60:.1f} мин)...")
                if attempt < RETRIES:
                    time.sleep(wait)
                    continue
                return None
            else:
                wait = 10 * attempt
                print(f"   ⚠ Ошибка (попытка {attempt}): {e}")
                if attempt < RETRIES:
                    time.sleep(wait)
                    continue
                return []

    return []


def extract_id(uri: str) -> str:
    return uri.split("/")[-1]


# ============================================================
# ШАГ 1: Все свойства (базовые данные)
# ============================================================

QUERY_PROPERTIES = """
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?property ?propertyType WHERE {
  ?property a wikibase:Property .
  ?property wikibase:propertyType ?propertyType .
}
"""


def step_properties(cache: dict) -> dict:
    """Шаг 1: сбор всех свойств с типами данных."""
    if "properties" in cache["steps_completed"] and cache["properties"]:
        print("\n[1/6] Пропуск — свойства уже собраны")
        return cache["properties"]

    print("\n[1/6] Сбор всех свойств...")
    bindings = run_sparql(QUERY_PROPERTIES, "Все свойства", "properties")
    if bindings is None:
        return None

    properties = {}
    for b in bindings:
        pid = extract_id(b["property"]["value"])
        datatype = b.get("propertyType", {}).get("value", "").split("#")[-1]
        properties[pid] = {
            "id": pid,
            "label_en": "", "label_ru": "",
            "description_en": "", "description_ru": "",
            "datatype": datatype,
            "superproperties": [], "subproperties": [],
            "domain": [], "range": [],
            "inverse": None,
        }

    cache["properties"] = properties
    cache["steps_completed"].add("properties")
    save_cache(cache)
    print(f"   ✓ Собрано свойств: {len(properties):,}")
    return properties


# ============================================================
# ШАГ 2: Иерархия свойств (P1647)
# ============================================================

QUERY_HIERARCHY = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
SELECT ?property ?superproperty WHERE {
  ?property wdt:P1647 ?superproperty .
}
"""


def step_hierarchy(properties: dict, cache: dict) -> bool:
    """Шаг 2: сбор иерархии свойств."""
    if "hierarchy" in cache["steps_completed"]:
        print("\n[2/6] Пропуск — иерархия уже собрана")
        return True

    print("\n[2/6] Сбор иерархии свойств...")
    print(f"   Ожидание {REQUEST_DELAY} сек перед запросом...")
    time.sleep(REQUEST_DELAY)

    bindings = run_sparql(QUERY_HIERARCHY, "Иерархия свойств", "hierarchy")
    if bindings is None:
        return False

    for b in bindings:
        pid = extract_id(b["property"]["value"])
        sid = extract_id(b["superproperty"]["value"])
        if pid in properties:
            properties[pid]["superproperties"].append(sid)
        if sid in properties and pid not in properties[sid]["subproperties"]:
            properties[sid]["subproperties"].append(pid)

    cache["steps_completed"].add("hierarchy")
    cache["properties"] = properties
    save_cache(cache)
    return True


# ============================================================
# ШАГ 3: Domain ограничения (ИСПРАВЛЕННЫЙ ЗАПРОС v2)
# ============================================================

# ПРАВИЛЬНЫЙ запрос: используем Q21503250 (subject type constraint)
# и квалификатор P2308 (class)
QUERY_DOMAIN = """
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>

SELECT ?property ?domainClass WHERE {
  ?property p:P2302 ?constraint .
  ?constraint ps:P2302 wd:Q21503250 .
  ?constraint pq:P2308 ?domainClass .
}
"""


def step_domain(properties: dict, cache: dict) -> bool:
    """Шаг 3: сбор ограничений типа субъекта (domain)."""
    if "domain" in cache["steps_completed"]:
        print("\n[3/6] Пропуск — domain уже собран")
        return True

    print("\n[3/6] Сбор domain ограничений (subject type constraint)...")
    print(f"   Ожидание {REQUEST_DELAY} сек...")
    time.sleep(REQUEST_DELAY)

    bindings = run_sparql(QUERY_DOMAIN, "Domain-ограничения (Q21503250 + P2308)", "domain")
    if bindings is None:
        return False

    count = 0
    for b in bindings:
        pid = extract_id(b["property"]["value"])
        domain_id = extract_id(b["domainClass"]["value"])
        if pid in properties and domain_id not in properties[pid]["domain"]:
            properties[pid]["domain"].append(domain_id)
            count += 1

    print(f"   ✓ Добавлено domain-связей: {count:,}")

    cache["steps_completed"].add("domain")
    cache["properties"] = properties
    save_cache(cache)
    return True

# ============================================================
# ШАГ 4: Range ограничения (ИСПРАВЛЕННЫЙ ЗАПРОС)
# ============================================================

QUERY_RANGE = """
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>

SELECT ?property ?rangeClass WHERE {
  ?property p:P2302 ?constraint .
  ?constraint ps:P2302 wd:Q21502838 .
  ?constraint pq:P2305 ?rangeClass .
}
"""


def step_range(properties: dict, cache: dict) -> bool:
    """Шаг 4: сбор ограничений типа значения (range)."""
    if "range" in cache["steps_completed"]:
        print("\n[4/6] Пропуск — range уже собран")
        return True

    print("\n[4/6] Сбор range ограничений...")
    print(f"   Ожидание {REQUEST_DELAY} сек...")
    time.sleep(REQUEST_DELAY)

    bindings = run_sparql(QUERY_RANGE, "Range-ограничения", "range")
    if bindings is None:
        return False

    count = 0
    for b in bindings:
        pid = extract_id(b["property"]["value"])
        range_id = extract_id(b["rangeClass"]["value"])
        if pid in properties and range_id not in properties[pid]["range"]:
            properties[pid]["range"].append(range_id)
            count += 1

    print(f"   ✓ Добавлено range-связей: {count:,}")

    cache["steps_completed"].add("range")
    cache["properties"] = properties
    save_cache(cache)
    return True


# ============================================================
# ШАГ 5: Обратные свойства (P1696)
# ============================================================

QUERY_INVERSE = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?property ?inverse WHERE {
  ?property a wikibase:Property .
  ?property wdt:P1696 ?inverse .
}
"""


def step_inverse(properties: dict, cache: dict) -> bool:
    """Шаг 5: сбор обратных свойств."""
    if "inverse" in cache["steps_completed"]:
        print("\n[5/6] Пропуск — inverse уже собран")
        return True

    print("\n[5/6] Сбор обратных свойств...")
    print(f"   Ожидание {REQUEST_DELAY} сек...")
    time.sleep(REQUEST_DELAY)

    bindings = run_sparql(QUERY_INVERSE, "Обратные свойства", "inverse")
    if bindings is None:
        return False

    count = 0
    for b in bindings:
        pid = extract_id(b["property"]["value"])
        inverse_id = extract_id(b["inverse"]["value"])
        if pid in properties:
            properties[pid]["inverse"] = inverse_id
            count += 1

    print(f"   ✓ Добавлено обратных свойств: {count:,}")

    cache["steps_completed"].add("inverse")
    cache["properties"] = properties
    save_cache(cache)
    return True


# ============================================================
# ШАГ 6: Названия на английском и русском (с кэшированием)
# ============================================================

def step_labels(properties: dict, cache: dict) -> bool:
    """
    Шаг 6: сбор названий и описаний на английском и русском.
    Использует wbgetentities REST API (не лимитируется SPARQL rate-limit).
    Прогресс кэшируется — можно прерывать и продолжать.
    """
    print("\n[6/6] Сбор названий и описаний (англ + рус)...")

    # Определяем, какие свойства ещё не имеют лейблов
    pids_to_fetch = [
        pid for pid, info in properties.items()
        if pid not in cache["labels_fetched"]
    ]
    print(f"   Всего свойств: {len(properties):,}")
    print(f"   Уже получено: {len(cache['labels_fetched']):,}")
    print(f"   Осталось получить: {len(pids_to_fetch):,}")

    if not pids_to_fetch:
        print("   ✓ Все лейблы уже получены")
        return True

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    batches = [pids_to_fetch[i:i + LABEL_BATCH_SIZE]
               for i in range(0, len(pids_to_fetch), LABEL_BATCH_SIZE)]

    en_new = 0
    ru_new = 0
    skipped = 0

    iterator = tqdm(batches, desc="   Лейблы", ncols=100) if tqdm else batches

    for batch_idx, batch in enumerate(iterator):
        params = {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "format": "json",
            "props": "labels|descriptions",
            "languages": "en|ru",
        }

        success = False
        for attempt in range(LABEL_RETRIES):
            try:
                resp = session.get(API_URL, params=params, timeout=30)

                # Обработка 429 отдельно
                if resp.status_code == 429:
                    wait = LABEL_DELAY * (attempt + 1) * 5  # длиннее для REST API
                    if tqdm:
                        tqdm.write(f"\n   ⚠ 429 rate limit, ждём {wait} сек...")
                    else:
                        print(f"\n   ⚠ 429 rate limit, ждём {wait} сек...")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()

                for pid, entity in data.get("entities", {}).items():
                    if pid not in properties:
                        continue

                    labels = entity.get("labels", {})
                    descs = entity.get("descriptions", {})

                    if "en" in labels:
                        properties[pid]["label_en"] = labels["en"].get("value", "")
                        en_new += 1
                    if "en" in descs:
                        properties[pid]["description_en"] = descs["en"].get("value", "")

                    if "ru" in labels:
                        properties[pid]["label_ru"] = labels["ru"].get("value", "")
                        ru_new += 1
                    if "ru" in descs:
                        properties[pid]["description_ru"] = descs["ru"].get("value", "")

                    cache["labels_fetched"].add(pid)

                success = True
                break

            except Exception as e:
                if attempt < LABEL_RETRIES - 1:
                    wait = LABEL_DELAY * (attempt + 1)
                    time.sleep(wait)
                else:
                    if tqdm:
                        tqdm.write(f"\n   ⚠ Пропуск батча {batch_idx}: {e}")
                    else:
                        print(f"\n   ⚠ Пропуск батча {batch_idx}: {e}")
                    skipped += len(batch)

        if success:
            # Сохраняем прогресс каждые 20 батчей
            if batch_idx % 20 == 0:
                cache["properties"] = properties
                save_cache(cache)

        time.sleep(LABEL_DELAY)

    # Финальное сохранение
    cache["properties"] = properties
    cache["steps_completed"].add("labels")
    save_cache(cache)

    print(f"\n   ✓ Новых английских названий: {en_new:,}")
    print(f"   ✓ Новых русских названий:    {ru_new:,}")
    if skipped:
        print(f"   ⚠ Пропущено ID: {skipped:,}")

    return True


# ============================================================
# СТАТИСТИКА И СОХРАНЕНИЕ
# ============================================================

def print_statistics(properties: dict) -> None:
    """Печатает финальную статистику."""
    print("\n" + "=" * 70)
    print("СТАТИСТИКА СХЕМЫ СВОЙСТВ")
    print("=" * 70)

    total = len(properties)
    with_hierarchy = sum(1 for p in properties.values() if p["superproperties"])
    with_domain = sum(1 for p in properties.values() if p["domain"])
    with_range = sum(1 for p in properties.values() if p["range"])
    with_inverse = sum(1 for p in properties.values() if p["inverse"])
    with_en = sum(1 for p in properties.values() if p["label_en"])
    with_ru = sum(1 for p in properties.values() if p["label_ru"])

    # Подсчёт всех связей
    total_domain = sum(len(p["domain"]) for p in properties.values())
    total_range = sum(len(p["range"]) for p in properties.values())
    total_hier = sum(len(p["superproperties"]) for p in properties.values())

    print(f"   Всего свойств:              {total:,}")
    print(f"   С английским названием:     {with_en:,} ({with_en/total*100:.1f}%)")
    print(f"   С русским названием:        {with_ru:,} ({with_ru/total*100:.1f}%)")
    print(f"   С иерархией:                {with_hierarchy:,} ({total_hier:,} связей)")
    print(f"   С domain-ограничениями:     {with_domain:,} ({total_domain:,} связей)")
    print(f"   С range-ограничениями:      {with_range:,} ({total_range:,} связей)")
    print(f"   С обратным свойством:       {with_inverse:,}")

    # Распределение по типам данных
    datatype_counts = defaultdict(int)
    for p in properties.values():
        datatype_counts[p["datatype"]] += 1

    if datatype_counts:
        print(f"\n   Распределение по типам данных:")
        for dt, count in sorted(datatype_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"      • {dt}: {count:,}")


def save_schema(properties: dict, output_path: str) -> None:
    """Сохраняет финальную схему."""
    schema = {
        "description": "Онтологическая схема свойств Wikidata (англ + рус)",
        "stats": {
            "total_properties": len(properties),
            "with_en_label": sum(1 for p in properties.values() if p["label_en"]),
            "with_ru_label": sum(1 for p in properties.values() if p["label_ru"]),
            "with_hierarchy": sum(1 for p in properties.values() if p["superproperties"]),
            "with_domain": sum(1 for p in properties.values() if p["domain"]),
            "with_range": sum(1 for p in properties.values() if p["range"]),
            "with_inverse": sum(1 for p in properties.values() if p["inverse"]),
            "total_domain_links": sum(len(p["domain"]) for p in properties.values()),
            "total_range_links": sum(len(p["range"]) for p in properties.values()),
        },
        "properties": properties,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    print(f"\n✅ Сохранено: {output_path}")
    print(f"   Размер: {size_mb:.2f} МБ")


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    print("=" * 70)
    print("Извлечение полной онтологической схемы свойств Wikidata")
    print("Финальная версия с исправленными запросами")
    print("Задержки: 70 сек между SPARQL-запросами")
    print("Прогресс сохраняется — можно прерывать и продолжать")
    print("=" * 70)

    start_time = time.time()
    cache = load_cache()

    # Шаг 1: свойства
    properties = step_properties(cache)
    if properties is None:
        print("\n⚠ Не удалось получить свойства. Запустите позже.")
        return

    # Шаги 2-5: SPARQL с длинными задержками
    failed_step = None
    steps = [
        (step_hierarchy, "hierarchy"),
        (step_domain, "domain"),
        (step_range, "range"),
        (step_inverse, "inverse"),
    ]

    for step_func, step_name in steps:
        success = step_func(properties, cache)
        if not success:
            failed_step = step_name
            print(f"\n⚠ Не удалось выполнить шаг: {step_name}")
            print(f"   Прогресс сохранён. Запустите позже, чтобы продолжить.")
            break

    # Шаг 6: лейблы (работает всегда через REST API)
    if failed_step is None:
        step_labels(properties, cache)

    # Финальная статистика
    print_statistics(properties)

    # Сохранение
    save_schema(properties, OUTPUT_FILE)

    elapsed = time.time() - start_time
    print(f"\n⏱ Общее время: {elapsed:.1f} сек ({elapsed/60:.1f} мин)")

    if failed_step:
        print(f"\n⚠ Прервано на шаге: {failed_step}")
        print("   Запустите скрипт снова — он продолжит с этого места.")
    else:
        print("\n🎉 ВСЕ ДАННЫЕ УСПЕШНО СОБРАНЫ!")


if __name__ == "__main__":
    main()
