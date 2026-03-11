# Vigilios — Project Research & Design Document

> **"나 대신 세상을 지켜보는 눈"**
> 라틴어 *Vigilo* = "I watch / I am awake"
> 프로젝트명 Vigilios = 고대 파수꾼, 깊이 보는 존재의 느낌. 냉정하고 묵직한 권위감.

---

## 1. 프로젝트 탄생 배경 및 전략적 결정

### 핵심 컨셉
"차갑게 세상이 어떻게 돌아가는지 본다." 종교·무역·경제시장·정치·사건사고를 **연결해서 읽는** 엔진.

### 전략적 결정 (플랫폼 vs 파이프라인)
- ❌ 플랫폼(웹 뉴스 소비 서비스) 먼저 → 플랫폼은 좋은 분석이 있어야 가치가 있음. 없으면 그냥 RSS 리더.
- ✅ **분석 파이프라인 먼저** → 이메일 브리핑으로 검증 → 품질 확인 후 웹 프론트엔드 → 구독 서비스
- 정보 누락은 플랫폼이 아니라 **소스 선택 + RAG 품질** 문제.

---

## 2. 전체 로드맵

```
Stage 1 (현재): Vigilios World Engine
  → 국제정치·경제·무역·종교·사건사고를 매일 아침 8시 KST 수집·분석·이메일 발송
  → 이메일 본문: 핵심 요약 (Gap 분석 수준까지)
  → 첨부파일: DOCX 전체 분석 보고서

Stage 2 (미래): Signal Extraction Engine
  → 음모론·대안 매체에서 팩트 핵심(kernel) 추출
  → Stage 1의 객관적 베이스라인 vs 노이즈 비교 분석
  → 음모론이 맞았던 사례 누적 → 신뢰도 가중치 학습

Stage 3 (미래): 통합 인텔리전스 플랫폼
  → 웹 서비스 프론트엔드
  → 구독형 서비스 (로그인, 구독 티어)
  → Knowledge Graph 시각화
```

---

## 3. Stage 1 파이프라인 설계

### 파이프라인 흐름 (Gap Engine 패턴 적용)

```
collect → dedup → enrich → score → select → AI analyze → save → email
```

Gap Engine과 동일하게:
- **Steps 1–6 (collect~select): 100% 결정론적**
- **Steps 7–8 (AI~email): AI + 이메일**
- AI는 요약·연결고리 분석만. 스코어나 선정을 변경하지 않음.

### 상세 파이프라인

```
┌─────────────────────────────────────────────────────┐
│                  COLLECTORS LAYER                    │
│  RSSCollector (feedparser + trafilatura)             │
│  GDELTCollector (BigQuery/API) — 선택적              │
│  ACLEDCollector (분쟁 이벤트 API) — 선택적           │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│                  DEDUP LAYER                         │
│  L1: URL 정규화 (SHA-256 canonical URL)              │
│  L2: SimHash 해밍거리 ≤4 (근사 중복)                 │
│  L3: 문장 임베딩 코사인 유사도 ≥0.85 (동일 사건 클러스터) │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│                  ENRICHMENT LAYER                    │
│  SourceCredibilityScorer (MBFC/AllSides DB 기반)     │
│  NERExtractor (spaCy: 국가·기관·인물)                │
│  TopicClassifier (CAMEO 코드 기반, BART-MNLI)        │
│  PMESIITagger (정치·군사·경제·사회·정보·인프라)       │
│  FringeSignalScorer (도메인 연령, 교차검증 수)        │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│                  SCORING LAYER (결정론적)             │
│  ImportanceScore = credibility×0.35                  │
│                  + corroboration×0.25                │
│                  + actor_significance×0.25           │
│                  + novelty×0.15                      │
│  RiskScore (PMESII 도메인별 심각도 가중치)            │
│  BiasAdjustedScore (단일 소스 기사 패널티)            │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│                  SELECTOR                            │
│  PMESII 도메인별 Top 3                               │
│  국가/지역별 최대 2건                                 │
│  Fringe kernel 확인된 경우 1건 포함                   │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│               AI ANALYSIS LAYER (Gemini)             │
│  SITREP: 기사 텍스트 기반, 그라운딩 없음              │
│  Analysis: 클러스터 기반 연결고리 분석                 │
│  Enrichment: 그라운딩, 최대 5건만                     │
│  출력: 구조화 JSON (PMESII 태그 + 심각도 포함)        │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│               OUTPUT / EMAIL LAYER                   │
│  이메일 본문: 카테고리별 핵심 요약 (잘리지 않는 길이)  │
│  DOCX 첨부: 전체 분석 보고서 (연결고리 포함)          │
│  JSON: run_metadata + story_candidates               │
│  reports/YYYY-MM/ 저장                               │
└─────────────────────────────────────────────────────┘
```

### 커버 토픽 — 5개 카테고리 (PMESII 매핑)

| 카테고리 | PMESII | 설명 | 주요 소스 |
|---|---|---|---|
| 국제정치 | Political | 정상회담, 선거, 외교, 군사 | Reuters, AP, BBC World |
| 경제·시장 | Economic | 금리, 환율, 주요 지표, 기업 | FT, Bloomberg RSS, WSJ |
| 무역·지정학 | Economic+Military | 관세, 제재, 공급망, 분쟁 | SCMP, Al Jazeera, Nikkei Asia |
| 사건·사고 | Social+Military | 테러, 재난, 사회 갈등 | AP Breaking, Reuters Alerts |
| 종교·문화 | Social+Information | 종교 갈등, 문명 충돌, 이념 | The Economist, Foreign Affairs |

### AI 분석 핵심 — 카테고리 간 연결고리

단순 요약이 아니라 **도메인 교차 인과관계**를 분석:
```
무역 갈등 → 공급망 재편 → 특정 지역 경제 압박 → 종교 갈등 심화
금리 인상 → 신흥국 부채 위기 → 정치 불안 → 이민·난민 증가
에너지 제재 → 유럽 인플레이션 → 극우 정당 부상 → NATO 균열
```

Stratfor 3단계 출력 구조 적용:
1. **SITREP** (상황 보고): 무슨 일이 있었나, 1~3문장, 분석 없음
2. **Analysis** (분석): 무슨 의미인가, 200~500자, 연결고리 포함
3. **Forecast** (전망): 무슨 일이 일어날 것인가, 조건부 시나리오

### 발송 스펙
- **주기**: 매일 오전 8시 KST (UTC 23:00 전날)
- **형식**: 이메일 본문 (카테고리별 핵심 요약, SITREP 수준) + DOCX 첨부 (전체 Analysis + Forecast)
- **수신자**: 개발자(subscribers.json) / 고객(customers.json) 분리

---

## 4. 설계 철학 (Gap Engine 청사진 적용)

### Core Principles

- **AI는 분석(presentation)만 수행** — 스코어링, 선정은 100% 결정론적. AI가 ImportanceScore나 선정을 변경해서는 안 됨.
- **같은 입력 → 같은 출력** — 재현 가능한 파이프라인. 모든 임계값은 `vigilios_rules.json`에서 관리.
- **중간 파일 없이 메모리 처리** — 최종 결과만 `reports/YYYY-MM/`에 저장.
- **파일 하나당 핵심 기능만 담아 모듈화** — 파일당 200줄 이하. 초과 시 승인 필요.
- **임계값은 코드에 하드코딩하지 않음** — 반드시 `vigilios_rules.json`에 추가, `VigiliosRules` 클래스로 참조.
- **AI 실패는 치명적이지 않음** — AI 없이 SITREP만 이메일 발송 후 계속 진행.
- **그라운딩은 아껴 쓴다** — 검색 그라운딩은 $35/1,000건. RSS로 수집 후 Top 3~5건만 그라운딩으로 보강.

### Gap Engine과의 차이점

| | Gap Investment Engine | Vigilios |
|---|---|---|
| 데이터 소스 | yfinance (주가) | RSS + GDELT + ACLED |
| 분류 기준 | 섹터 (GICS) | PMESII 도메인 |
| 핵심 출력 | Top 5 종목 | 도메인별 Top 3 이슈 |
| 결정론적 요소 | 스코어링·선정 | 소스 선정·토픽 분류·ImportanceScore |
| AI 역할 | 요약만 | SITREP + 연결고리 Analysis + Forecast |
| 중복 처리 | 없음 (주식은 고유) | 3단계 Dedup 필수 |
| 편향 처리 | 없음 | SourceCredibilityScorer + BiasAdjustedScore |

---

## 5. 기술 스택

| 역할 | 기술 | 비고 |
|---|---|---|
| RSS 수집 | `feedparser` | 오작동 피드 처리 포함 |
| 본문 추출 | `trafilatura` | newspaper3k보다 정확도 높음 |
| 중복 제거 | `simhash`, `datasketch` (MinHash LSH) | |
| 임베딩/클러스터 | `sentence-transformers` (all-MiniLM-L6-v2) | |
| NER | `spaCy` (en_core_web_trf) | 국가·기관·인물 추출 |
| 토픽 분류 | `facebook/bart-large-mnli` (HuggingFace) | 학습 데이터 불필요 |
| AI 분석 | Gemini 2.0 Flash + Google Search grounding | 그라운딩 최대 5건/run |
| 보고서 생성 | `python-docx` | |
| 이메일 발송 | `smtplib` (Gmail SMTP) | |
| 자동화 | GitHub Actions (cron) | |
| 그래프 DB (미래) | `networkx` → `neo4j` | Stage 2 준비 |

---

## 6. 프로젝트 구조

```
Vigilios/
├── main.py                      # 파이프라인 오케스트레이터
├── auto_daily_report.py         # GitHub Actions 진입점
├── research.md                  # 이 파일
├── requirements.txt
├── config/
│   ├── vigilios_rules.json      # Single source of truth (임계값·가중치)
│   ├── sources.json             # RSS 피드 URL + 편향 등급 목록
│   ├── topics.json              # CAMEO 토픽 분류 규칙
│   ├── email_config.json        # (gitignored)
│   ├── subscribers.json         # 개발자 수신자 (gitignored)
│   └── customers.json           # 고객 수신자 (gitignored)
├── collectors/
│   ├── base_collector.py        # ThreadPoolExecutor 공통 래퍼
│   ├── rss_collector.py         # RSS + 본문 추출
│   └── gdelt_collector.py       # GDELT (선택적)
├── engine/
│   ├── rules.py                 # VigiliosRules 클래스
│   ├── deduplicator.py          # 3단계 중복 제거
│   ├── enricher.py              # NER + 토픽 분류 + PMESII 태깅
│   ├── scorer.py                # ImportanceScore + RiskScore
│   └── selector.py              # 도메인별 Top N 선정
├── ai/
│   └── analyzer.py              # Gemini SITREP + Analysis + Forecast
├── email_sender/
│   ├── sender.py
│   ├── templates.py
│   └── report_docx.py
└── reports/                     # YYYY-MM/ 구조로 저장
```

### Output Files (`reports/YYYY-MM/`)

| 파일 | 내용 |
|---|---|
| `snapshot_raw.json` | 수집된 전체 기사 (dedup 전) |
| `story_clusters.json` | 동일 사건 클러스터 |
| `scored_universe.csv` | 전체 기사 스코어 |
| `top_stories.json` | 선정된 도메인별 Top 기사 |
| `run_metadata.json` | 수집 통계·필터 비율·선정 결과 |
| `report_YYYYMMDD.docx` | 전체 분석 보고서 (이메일 첨부) |

---

## 7. vigilios_rules.json 구조 (예정)

```json
{
  "collection": {
    "rss_poll_interval_minutes": 15,
    "max_age_hours": 48,
    "min_article_length_chars": 200
  },
  "dedup": {
    "simhash_hamming_threshold": 4,
    "semantic_cosine_threshold": 0.85,
    "story_cluster_window_hours": 24
  },
  "credibility": {
    "mbfc_minimum_factual_score": 0.4,
    "corroboration_minimum_sources": 2,
    "domain_age_minimum_days": 180
  },
  "scoring": {
    "importance_weights": {
      "credibility": 0.35,
      "corroboration": 0.25,
      "actor_significance": 0.25,
      "novelty": 0.15
    }
  },
  "selection": {
    "top_n_per_pmesii_domain": 3,
    "max_per_country": 2,
    "include_fringe_if_kernel_confirmed": true
  },
  "ai": {
    "model": "gemini-2.0-flash",
    "grounding_enabled": true,
    "grounding_max_calls_per_run": 5,
    "temperature": 0.1
  }
}
```

---

## 8. 핵심 리서치 — 분야별 참고 프레임워크

### 8-1. 미디어 편향 프레임워크

**AllSides** 방법론:
- 블라인드 서베이 + 편집 리뷰 + 독립 리뷰 + 커뮤니티 피드백
- 편향 신호: 기사 선택(무엇을 덮고 무엇을 안 덮나), 헤드라인 프레이밍, 인용 소스, 누락, 스핀

**오픈소스 편향 DB:**
- `ds4sd/MediaBias` (HuggingFace) — ~2,000개 소스, MBFC 기반
- Ad Fontes Media Bias Chart CSV
- `plenaryapp/awesome-rss-feeds` (GitHub) — 성향별 RSS OPML 모음

### 8-2. 지정학 분석 프레임워크

**PMESII 프레임워크** (미군/NATO):
Political · Military · Economic · Social · Information · Infrastructure
→ Vigilios 기사 태깅 기준으로 채택. 교차 도메인 연결 분석의 핵심 구조.

**ACH (Analysis of Competing Hypotheses)** — CIA 리처즈 호이어 개발:
- 모든 가설 나열 → 증거 매핑 → 불일치 가장 많은 가설 제거
- **확인 증거보다 반증 증거를 찾는다** — Stage 2 음모론 분석에 직접 적용 가능

**GDELT**: 15분 단위 업데이트, 100개 이상 언어, BigQuery 무료 티어.
CAMEO 이벤트 코딩 (300+ 이벤트 유형) — 토픽 분류 기준으로 채택.

**ACLED**: 분쟁·시위 이벤트 실시간 API. 무료.

### 8-3. Gemini + Google Search Grounding

**작동 방식**: Gemini가 자체적으로 검색 쿼리 생성 → Google 실시간 검색 → 결과 요약 → `grounding_metadata`에 소스 포함 반환.

**비용 구조 (2025 기준)**:
- `gemini-2.0-flash` 무료: 15 RPM, 1,500 RPD
- 검색 그라운딩: **$35 / 1,000건** (토큰 비용과 별도)
- 설계 원칙: RSS로 벌크 수집(무료) → 그라운딩은 Top 3~5건 보강에만 사용

---

## 9. 환경 변수 및 설정

- `GOOGLE_API_KEY` — Gemini + Google Search grounding 필수
- `config/email_config.json` — SMTP 설정 (gitignored)
- `config/subscribers.json` — 개발자 수신자 (gitignored)
- `config/customers.json` — 고객 수신자 (gitignored)

---

## 10. CLI 명령어 (예정)

```bash
# 전체 파이프라인 (AI 분석 + 이메일)
python main.py

# 이메일 없이
python main.py --no-email

# AI 없이 (SITREP만)
python main.py --no-ai

# 특정 수신 대상
python main.py --target developers
python main.py --target customers

# 자동 일일 실행 (GitHub Actions)
python auto_daily_report.py
```

---

## 11. Known Limitations (예상)

- **ImportanceScore 가중치** 초기값은 추정치. 실제 운용 후 조정 필요.
- **BART-MNLI 분류** — GPU 없으면 느림. 초기에는 키워드 규칙으로 대체 후 점진적 도입.
- **GDELT/ACLED API** — 선택적. v1에서는 RSS만으로 시작.
- **그라운딩 비용** — 운용 초기에는 `grounding_max_calls_per_run: 3`으로 제한.
- **한국어 소스** — v1은 영어 소스만. 한국어 NER/분류는 별도 모델 필요.

---

## 12. 학술 논문 기반 설계 원칙

### 설계 원칙 (논문 기반)

| 원칙 | 근거 논문 | 적용 방법 |
|---|---|---|
| CAMEO 2단계까지만 사용 | Mirai (2024) | 3단계는 노이즈 과다, 분류 오류율 높음 |
| 다자관계 NER 필수 | WORLDREP (2024) | 양자관계만 추출 시 다자 지정학 놓침 |
| LLM 단독 예측 금지 | Do LLMs Know Conflict (2025) | ACLED/GDELT 구조화 데이터 컨텍스트 주입 필수 |
| Gemini 지정학 편향 인식 | Echoes of Power (2025) | 중요 이슈에서 교차 소스 검증 의무화 |
| 편향을 다차원으로 저장 | Decoding News Bias (2025) | 단일 점수 아닌 유형별 편향 딕셔너리 |
| KG에 이벤트 주입 후 RAG | EventRAG (ACL 2025) | 텍스트 직주입보다 이벤트 KG 서브그래프가 효과적 |
| 신뢰도 지표는 실전 검증된 것만 | What Signals Matter (2024) | 고비용 저효율 신호 제거 |

### 논문 참조 목록

- Mirai: LLM Event Forecasting (arXiv:2407.01231)
- WORLDREP: International Events (arXiv:2411.14042)
- News Embedding for Geopolitical Prediction (arXiv:2405.13071)
- Economic Causal-Chain Text Mining (ACL 2019)
- Event Causality Identification Survey (arXiv:2411.10371)
- Causal News Corpus CNC-V2 / RECESS
- ViEWS: Political Violence Early-Warning (Journal of Peace Research, 2019)
- Do LLMs Know Conflict? (arXiv:2505.09852)
- HydraNet Conflict Forecasting (arXiv:2506.14817)
- Temporal Structures for Geopolitical Forecasting (arXiv:2601.00430)
- U.S. Entity List Temporal Graph Analysis (arXiv:2510.21962)
- EventRAG: Event Knowledge Graphs (ACL 2025)
- Political Bias in Western Media LLMs (arXiv:2601.06132)
- Decoding News Bias: Multi Bias Detection (arXiv:2501.02482)
- Echoes of Power: Geopolitical Bias in LLMs (arXiv:2503.16679)
- What Signals Matter for Misinformation? (arXiv:2512.02552)
- Linked Credibility Reviews (arXiv:2008.12742)
- Credibility Indicators (Semantic Scholar)
- Geopolitical Conflicts Impact on Trade (arXiv:2203.12173)
- MENDEL: Newspaper Crisis Signaling (NAACL 2024)
- CASE: Socio-political Events Survey (ACL 2024)

---

## 13. 주요 참고 자료

| 분야 | 소스 |
|---|---|
| RSS 파싱 | https://feedparser.readthedocs.io |
| 본문 추출 | https://trafilatura.readthedocs.io |
| MinHash/LSH | https://github.com/ekzhu/datasketch |
| GDELT | https://www.gdeltproject.org/data.html |
| CAMEO 이벤트 코드 | http://data.gdeltproject.org/documentation/CAMEO.Manual.BETA.pdf |
| ACLED 분쟁 데이터 | https://acleddata.com |
| AllSides 방법론 | https://www.allsides.com/media-bias/media-bias-rating-methods |
| MBFC HuggingFace | https://huggingface.co/datasets/ds4sd/MediaBias |
| Ad Fontes 편향 CSV | https://adfontesmedia.com/download-bias-chart-data/ |
| CIA 분석 심리학 | https://www.cia.gov/resources/csi/books-monographs/psychology-of-intelligence-analysis-2/ |
| RAND Truth Decay | https://www.rand.org/research/projects/truth-decay.html |
| CFR 분쟁 트래커 | https://www.cfr.org/global-conflict-tracker |
| ViEWS 조기경보 | https://github.com/prio-data/viewser |
| Gemini 그라운딩 | https://ai.google.dev/gemini-api/docs/grounding |
| SIFT 검증 방법 | https://cor.inquirygroup.org/digital-literacy/sift |
| 검증 핸드북 | https://verificationhandbook.com |
| Awesome RSS Feeds | https://github.com/plenaryapp/awesome-rss-feeds |

---

## 14. 다음 단계

1. `config/sources.json` — RSS 피드 소스 목록 확정 (편향 등급 포함)
2. `config/vigilios_rules.json` — 임계값 초기값 설정
3. `collectors/rss_collector.py` — 수집기 구현 (feedparser + trafilatura)
4. `engine/deduplicator.py` — 3단계 중복 제거
5. `engine/scorer.py` — ImportanceScore 구현
6. `ai/analyzer.py` — SITREP + Analysis + Forecast 프롬프트 설계
7. `email_sender/report_docx.py` — DOCX 보고서 생성
8. GitHub Actions 워크플로우 (매일 UTC 23:00)
