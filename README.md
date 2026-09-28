# Wikidata Ontology Extractor

Extraction of an **ontological schema** from [Wikidata](https://www.wikidata.org/) for semantic table interpretation tasks: a hierarchy of topical classes, properties with domain/range constraints, and English/Russian labels and descriptions.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Data](https://img.shields.io/badge/Data-Wikidata-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 📋 Table of Contents

- [Motivation](#-motivation)
- [What Is Extracted](#-what-is-extracted)
- [Results](#-results)
- [Repository Structure](#-repository-structure)
- [Pipeline Architecture](#-pipeline-architecture)
- [Installation](#-installation)
- [Usage](#-usage)
- [Output Data Structure](#-output-data-structure)
- [Limitations and Notes](#-limitations-and-notes)
- [License and Sources](#-license-and-sources)
- [Authors](#-authors)

## 🎯 Motivation

For **semantic table interpretation** (mapping columns to classes, and relations between columns to ontology properties), a complete and clean ontological schema is required. Wikidata is the largest open knowledge graph, but:

- ❌ "*Raw*" Wikidata contains **metaclasses** and **system entities** (categories, templates, disambiguation pages) that interfere with interpretation
- ❌ The SPARQL endpoint cannot handle bulk queries (timeouts, 429 rate limiting)
- ❌ Full Wikidata dumps occupy 50–100 GB

**Solution**: a hybrid pipeline that uses prebuilt binary files from [zelph](https://zelph.org/) for the class hierarchy and targeted queries for properties.

## 📦 What Is Extracted

### Classes (`subClassOf` hierarchy / P279)

| Attribute | Description                             |
|-----------|-----------------------------------------|
| `id` | Q-identifier (e.g., `Q6256`)            |
| `label_en` / `label_ru` | Label in English and Russian            |
| `description_en` / `description_ru` | Description in English and Russian      |
| `ancestors` | All superclasses (*transitive closure*) |
| `edges` | Direct subclass relations               |

### Properties (full schema)

| Attribute | Description |
|-----------|-------------|
| `id` | P-identifier (e.g., `P36`) |
| `label_en` / `label_ru` | Label |
| `description_en` / `description_ru` | Description |
| `datatype` | Data type (`WikibaseItem`, `Quantity`, `Time`, etc.) |
| `superproperties` / `subproperties` | Property hierarchy (`P1647`) |
| `domain` | Classes the property applies to |
| `range` | Classes of property values |
| `inverse` | Inverse property (`P1696`) |

## 📊 Results

Data snapshot as of **2026**:

| Component | Value              |
|-----------|--------------------|
| 🏛 Topical classes | 582,467            |
| 🔗 Subclass relations | 669,213            |
| 🚫 Excluded metaclasses | 307,503            |
| ⚙️ Properties | 13,928             |
| 🇬🇧 Properties with English labels | 13,926 (100%)      |
| 🇷🇺 Properties with Russian labels | 9,066 (65%)        |
| 🎯 Properties with domain constraints | 9,045 (23,020 links) |
| 🎯 Properties with range constraints | 1,267 (6,509 links) |

## 📁 Repository Structure

```text
wikidata-ontology-extractor/
├── data/                                             # Данные проекта (результаты и промежуточные файлы)
│   ├── class_schema_sample.json                      # Небольшая выборка классов для быстрого просмотра и отладки
│   ├── class_schema_with_labels_and_descriptions.zip # Сжатая полная схема иерархии классов с названиями и описаниями на английском и русском языках
│   ├── hierarchy_export.txt                          # Сырой экспорт иерархии классов (ребра подклассов) из zelph
│   └── properties_schema_with_labels.json            # Полная схема свойств с названиями и описаниями на английском и русском языках
│
├── src/                                              # Исходный код проекта (скрипты извлечения и обработки)
│   ├── add_labels_and_descriptions.py                # Добавление названий и описаний на английском и русском языках к классам через Wikidata API
│   ├── extract_class_schema.py                       # Построение схемы иерархии классов из экспорта (фильтрация метаклассов, транзитивное замыкание)
│   ├── extract_properties.py                         # Сбор схемы свойств (иерархия, domain/range-ограничения, обратные свойства) через Wikidata API
│   ├── inspect_class_schema.py                       # Урезанный пример файла схемы иерархии классов (статистика, примеры, целостность)
│   └── wikidata-20260309-all-pruned-small-P279.bin   # Исходный бинарный файл zelph с иерархией классов (входные данные) - требует отдельного скачивания
│
├── .gitignore                                        # Исключения системы контроля версий (кэши, временные файлы)
├── LICENSE                                           # MIT-лицензия проекта
├── README.md                                         # Основная документация проекта с инструкциями по установке и использованию
└── requirements.txt                                  # Список Python-зависимостей проекта
```

## 🏗 Pipeline Architecture

**STEP 1: Class hierarchy**
- Source: zelph file `wikidata-20260309-all-pruned-small-P279.bin`
- Export via zelph REPL → `hierarchy_export.txt`
- Filter metaclasses (*transitively from roots*)
- Result: `class_schema.json`

**STEP 2: Class labels and descriptions**
- Source: Wikidata wbgetentities REST API
- Batches of 50, progress caching
- Result: `class_schema_with_labels_and_descriptions.json`

**STEP 3: Property schema**
- Source: SPARQL endpoint + wbgetentities API
- Hierarchy (`P1647`), domain (`Q21503250`+`P2308`), range, inverse
- Rate limiting: 70-second pauses between queries
- Result: `properties_schema_with_labels.json`

## 💻 Installation

### Requirements

- **Python 3.8+**
- **~5 GB** of free disk space (*for the data*)
- **~8 GB** of RAM (*for processing large files*)
- A stable internet connection (*for collecting labels and properties*)

### Step 1. Clone the repository

```bash
git clone https://github.com/YRL-AIDA/wikidata-ontology-extractor.git
cd wikidata-ontology-extractor
```

### Step 2. Virtual environment

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### Step 3. Dependencies

```bash
pip install -r requirements.txt
```

Contents of requirements.txt:

```requirements
SPARQLWrapper>=2.0.0
requests>=2.31.0
tqdm>=4.66.0
```

### Step 4. Install zelph (optional)

To extract the class hierarchy from scratch, you need [zelph](https://zelph.org/):

```bash
# Download the binary for your OS from the official website
# Verify the installation:
zelph --version
```

💡 *If you want to use the prebuilt files from this repository's releases (or from Hugging Face), installing zelph is not required.*

## 🚀 Usage

**Option A: Use prebuilt data**

Download the prebuilt files from the releases or from Hugging Face:

```bash
# Example download via hf
pip install huggingface_hub
hf download <user>/wikidata-ontology-extractor \
    unified_ontology.json \
    --repo-type dataset \
    --local-dir ./data
```

**Option B: Run the full pipeline**

**Step 1. Extract the class hierarchy from zelph**

1. Download the hierarchy file

```bash
hf download acrion/zelph \
    wikidata-20260309-all-pruned-small-P279.bin \
    --repo-type dataset --local-dir ./data
```

2. Launch zelph and export the edges

```bash
zelph
zelph> .load ./data/wikidata-20260309-all-pruned-small-P279.bin
zelph> .lang wikidata
```

In Janet mode (`%`):

```Janet
%
(def results (zelph/query (zelph/fact 'X "P279" 'Y)))
(def n (length results))
(with [f (file/open "data/hierarchy_export.txt" :w)]
  (each r results
    (file/write f (string (zelph/name (get r 'X)) "\t" (zelph/name (get r 'Y)) "\n"))))
(print "Export complete: " n " edges")
%
```

**Step 2. Build the clean class schema**

```bash
python src/extract_class_schema.py
```

Metaclasses are excluded (transitively from the roots: `Q16889133`, `Q15138389`, `Q19478619`, etc.), along with system entities.

Result: `data/class_schema.json`

**Step 3. Add class labels and descriptions**

```bash
python src/add_labels_descriptions.py
```

⏱ *Time: ~40–50 minutes. Progress is cached in `labels_cache.pkl` — you can interrupt and resume.*

Result: `data/class_schema_with_labels_and_descriptions.json`

**Step 4. Collect the property schema**

```bash
python src/extract_properties.py
```

⏱ *Time: ~30–40 minutes (due to pauses for working around SPARQL endpoint rate limiting). Progress is cached.*

Result: `data/properties_schema_with_labels.json`

**Step 5. Validate the results**

```bash
python src/inspect_class_schema.py
```

This prints statistics, shows class examples with descriptions, and saves a small sample for inspection.

Result: `data/class_schema_sample.json`

## 📄 Output Data Structure

Example for `class_schema_with_labels_and_descriptions.json`:

```json
{
  "edges": [
    { "child": "Q5", "parent": "Q154954" },
    { "child": "Q515", "parent": "Q486972" }
  ],
  "all_ancestors": {
    "Q5": ["Q154954", "Q559618", "Q729", "Q35120"],
    "Q515": ["Q486972", "Q56061", "Q35120"]
  },
  "class_info": {
    "Q5": {
      "label_en": "human",
      "label_ru": "человек",
      "description_en": "any member of Homo sapiens",
      "description_ru": "представитель вида Homo sapiens"
    },
    "Q515": {
      "label_en": "city",
      "label_ru": "город",
      "description_en": "large and permanent human settlement",
      "description_ru": "крупный населённый пункт"
    }
  },
  "stats": {
    "total_edges": 669213,
    "total_classes": 582467,
    "root_classes": 4218,
    "leaf_classes": 487305,
    "metaclasses_removed": 307503
  }
}
```

Example for `properties_schema_with_labels.json`:

```json
{
  "description": "Wikidata property ontological schema (EN + RU labels and descriptions)",
  "stats": {
    "total_properties": 13928,
    "with_en_label": 13926,
    "with_ru_label": 9066,
    "with_hierarchy": 1048,
    "with_domain": 9045,
    "with_range": 1267,
    "with_inverse": 208,
    "total_domain_links": 23020,
    "total_range_links": 6509
  },
  "properties": {
    "P36": {
      "id": "P36",
      "label_en": "capital",
      "label_ru": "столица",
      "description_en": "capital city of the subject",
      "description_ru": "столица или главный город объекта",
      "datatype": "WikibaseItem",
      "superproperties": ["P1376"],
      "subproperties": [],
      "domain": ["Q6256", "Q56061", "Q82794"],
      "range": ["Q515", "Q486972"],
      "inverse": "P1376"
    },
    "P31": {
      "id": "P31",
      "label_en": "instance of",
      "label_ru": "это частный случай понятия",
      "description_en": "that class of which this subject is a particular example and member",
      "description_ru": "данный элемент является примером следующего класса",
      "datatype": "WikibaseItem",
      "superproperties": [],
      "subproperties": ["P279"],
      "domain": [],
      "range": [],
      "inverse": null
    }
  }
}
```

## ⚠ Limitations and Notes

**Wikidata rate limiting**

The SPARQL endpoint may enter an aggressive mode of `1 request per minute`. The scripts automatically insert 70-second pauses and save progress to disk - if interrupted, simply restart the script.

**Constraint structure**

In the current version of Wikidata:

- **Domain constraints** use the type `Q21503250` (*subject type constraint*) with the qualifier `P2308` (*class*)
- **Range constraints** use the type `Q21502838` (*value type constraint*) with the qualifier `P2305`

This is important to keep in mind when updating the queries.

**Label coverage**

- **Classes**: English labels ~96%, Russian ~55% (*depends on the data snapshot*)
- **Properties**: English 100%, Russian ~65%

Classes without labels remain with empty fields - they can be identified only by Q-ID.

**File sizes**

| File | Size |
|-----------|---------|
| `hierarchy_export.txt` | ~20 MB  |
| `class_schema.json` | ~650 MB |
| `class_schema_with_labels_and_descriptions.json` | ~800 MB |
| `properties_schema_final.json` | ~7 MB   |

*Large files are not committed to the repository. Use releases, Git LFS, or Hugging Face.*

## 📚 License and Sources

**Data**

The data is extracted from [Wikidata](https://www.wikidata.org/) and is distributed under the [CC0 1.0 Universal license](https://creativecommons.org/publicdomain/zero/1.0/).

**Resources used**

- [Wikidata](https://www.wikidata.org/) — the open knowledge graph
- [Wikidata Query Service](https://query.wikidata.org/) — the SPARQL endpoint
- [zelph](https://zelph.org/) — a semantic network engine for working with dumps
- [zelph on Hugging Face](https://huggingface.co/datasets/acrion/zelph/) — prebuilt binary hierarchy files

**Code**

The project code is distributed under the MIT license.

## ✍ Authors

* [Nikita O. Dorodnykh](mailto:nikidorny@icc.ru)
* [Kirill V. Tobola](mailto:kirilltobola@icc.ru)