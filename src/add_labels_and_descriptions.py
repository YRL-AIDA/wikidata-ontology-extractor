"""
Добавляет английские и русские названия И ОПИСАНИЯ классов в class_schema.json.
Использует стабильный Wikidata API wbgetentities.
Кэширует прогресс на диск для возобновления.
"""

import json
import time
import pickle
import requests
from pathlib import Path
from tqdm import tqdm

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

INPUT_SCHEMA = "class_schema.json"
OUTPUT_SCHEMA = "class_schema_with_labels_and_descriptions.json"
CACHE_FILE = "labels_cache_with_descriptions.pkl"

API_URL = "https://www.wikidata.org/w/api.php"
BATCH_SIZE = 50
DELAY = 0.2
RETRIES = 3

LANGUAGES = "en|ru"


# ============================================================
# КЭШИРОВАНИЕ
# ============================================================

def load_cache() -> dict:
    p = Path(CACHE_FILE)
    if p.exists():
        with open(p, "rb") as f:
            return pickle.load(f)
    return {}


def save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(cache, f)


# ============================================================
# ПОЛУЧЕНИЕ ДАННЫХ ЧЕРЕЗ API
# ============================================================

def fetch_batch(qids: list, session: requests.Session) -> dict:
    """
    Получает лейблы И описания для батча Q-ID.
    Возвращает словарь {qid: {"en_label": ..., "ru_label": ..., "en_desc": ..., "ru_desc": ...}}.
    """
    params = {
        "action": "wbgetentities",
        "ids": "|".join(qids),
        "format": "json",
        "props": "labels|descriptions",
        "languages": LANGUAGES,
    }

    for attempt in range(RETRIES):
        try:
            resp = session.get(API_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            result = {}
            for qid, entity in data.get("entities", {}).items():
                labels = entity.get("labels", {})
                descriptions = entity.get("descriptions", {})

                en_label = labels.get("en", {}).get("value", "")
                ru_label = labels.get("ru", {}).get("value", "")
                en_desc = descriptions.get("en", {}).get("value", "")
                ru_desc = descriptions.get("ru", {}).get("value", "")

                result[qid] = {
                    "label_en": en_label,
                    "label_ru": ru_label,
                    "description_en": en_desc,
                    "description_ru": ru_desc,
                }
            return result

        except Exception as e:
            if attempt < RETRIES - 1:
                wait = 3 * (attempt + 1)
                print(f"\n   ⚠ Ошибка (попытка {attempt+1}): {e}, повтор через {wait} сек")
                time.sleep(wait)
                continue
            print(f"\n   ⚠ Не удалось получить батч, пропускаю")
            return {}


def fetch_all_data(qids: list) -> dict:
    """Получает лейблы и описания для всех Q-ID с кэшированием."""
    cache = load_cache()
    session = requests.Session()
    session.headers.update({
        "User-Agent": "ClassSchemaLabeler/2.0 (contact@example.com)"
    })

    missing = [q for q in qids if q not in cache]
    print(f"Всего классов: {len(qids):,}")
    print(f"Уже в кэше: {len(qids) - len(missing):,}")
    print(f"Нужно получить: {len(missing):,}")

    if not missing:
        print("Все данные уже в кэше!")
        return cache

    batches = [missing[i:i+BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]

    for batch in tqdm(batches, desc="Получение лейблов и описаний", ncols=100):
        result = fetch_batch(batch, session)
        cache.update(result)

        if len(cache) % (BATCH_SIZE * 100) == 0:
            save_cache(cache)

        time.sleep(DELAY)

    save_cache(cache)
    return cache


# ============================================================
# ОБНОВЛЕНИЕ СХЕМЫ
# ============================================================

def update_schema(schema: dict, data: dict) -> dict:
    """Добавляет лейблы и описания в структуру схемы."""
    all_classes = set(schema["all_ancestors"].keys())

    class_info = {}
    for qid in all_classes:
        info = data.get(qid, {})
        class_info[qid] = {
            "label_en": info.get("label_en", ""),
            "label_ru": info.get("label_ru", ""),
            "description_en": info.get("description_en", ""),
            "description_ru": info.get("description_ru", ""),
        }

    schema["class_info"] = class_info
    return schema


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    print("=" * 70)
    print("Добавление названий И ОПИСАНИЙ классов (англ + рус)")
    print("=" * 70)

    print("\n[1/3] Загрузка схемы...")
    with open(INPUT_SCHEMA, "r", encoding="utf-8") as f:
        schema = json.load(f)
    print(f"      Классов в схеме: {len(schema['all_ancestors']):,}")

    print("\n[2/3] Получение данных через Wikidata API...")
    all_qids = list(schema["all_ancestors"].keys())
    data = fetch_all_data(all_qids)

    # Статистика
    en_labels = sum(1 for v in data.values() if v.get("label_en"))
    ru_labels = sum(1 for v in data.values() if v.get("label_ru"))
    en_descs = sum(1 for v in data.values() if v.get("description_en"))
    ru_descs = sum(1 for v in data.values() if v.get("description_ru"))

    print(f"\n      Английских названий:    {en_labels:,}")
    print(f"      Русских названий:       {ru_labels:,}")
    print(f"      Английских описаний:    {en_descs:,}")
    print(f"      Русских описаний:       {ru_descs:,}")

    print("\n[3/3] Обновление схемы и сохранение...")
    schema = update_schema(schema, data)

    with open(OUTPUT_SCHEMA, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    size_mb = Path(OUTPUT_SCHEMA).stat().st_size / (1024 * 1024)
    print(f"\n{'='*70}")
    print(f"✅ ГОТОВО!")
    print(f"{'='*70}")
    print(f"Файл: {OUTPUT_SCHEMA}")
    print(f"Размер: {size_mb:.1f} МБ")


if __name__ == "__main__":
    main()
