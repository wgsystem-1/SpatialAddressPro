<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# 공개 LLM을 이용해서 주소 정제 솔루션을 개발하려고 한다.

상세한 개발 스택과 방법을 상세하게 조사해서 보고서를 작성해

공개(오픈소스·오픈웨이트) LLM과 기존 주소 API/라이브러리를 조합해서 “한국 주소 정제 솔루션”을 만드는 구조가 가장 현실적이다. 아래는 이를 전제로 한 개발 스택·아키텍처·구현 방법을 보고서 형태로 정리한 내용이다.[^1][^2][^3][^4][^5]

***

## 1. 전체 아키텍처 개요

주소 정제(Address Normalization) 파이프라인은 보통 다음 4단계 구조로 설계할 수 있다.[^6][^7]

1) 입력 수집·전처리

- 입력 소스: 명함 OCR, 사용자 입력, 기존 DB 덤프(CSV/Excel), 로그 데이터 등.
- 전처리: 공백·제어문자 제거, 한글/영문 분리, 특수문자 정규화, 인코딩 통합(UTF-8).[^8][^9]

2) 기본 주소 파싱·정규화 (규칙/통계 기반)

- 한국 도로명주소 API(juso.go.kr)로 1차 매칭 및 행정구역 코드/지번·도로명주소 확보.[^4][^10]
- libpostal 같은 통계기반 주소 파서로 일반적인 주소 토큰화/정규화 수행.[^11][^3][^5]
- 한국 특화용 Python 라이브러리(addresskr 등)로 도로명주소 구성요소 필드화.[^2][^12]

3) LLM 기반 주소 보정·보완

- 오픈 LLM(Llama, Qwen 등)을 로컬/서버에 올려 “이상치·불완전 주소”만 대상으로 재작성/보정.[^13][^1]
- Retrieval-Augmented Generation(RAG)로 자체 주소 마스터/행정동 코드 테이블을 참조해 보정 정확도 향상.[^14][^1]

4) 검증·저장·서비스

- 최종 주소에 행정동코드, 도로명코드, 우편번호, 좌표(geocoding)까지 맵핑 후 PostgreSQL/PostGIS에 저장.
- 정제 결과와 원본 주소를 함께 저장해 추적성 확보, 품질 리포트/대시보드 제공.[^15][^6]

***

## 2. 권장 기술 스택

### 2.1 코어 엔진·언어 스택

- 애플리케이션 언어
    - Python: 주소 API 연동, libpostal 바인딩, LLM 파이프라인, ETL 스크립트에 최적.[^2][^15][^14]
    - C\#/.NET: 사용자의 기존 기술 스택을 고려하면, CS 클라이언트·백오피스 UI·윈도우 서비스 구현에 유리.
- 데이터베이스
    - PostgreSQL + PostGIS: 주소 마스터, 행정구역, 품질 로그, 공간 검색(반경·버퍼 검증) 저장소로 사용.[^3][^15]
- 컨테이너·배포
    - Docker / Docker Compose: libpostal, LLM 서버, API 게이트웨이, Web UI를 각각 컨테이너화.[^5][^3][^14]
    - 필요 시 Kubernetes: SaaS로 확장 시 오토스케일링·롤링업데이트에 유리.[^13][^14]


### 2.2 주소 파싱·정규화 라이브러리

- 한국 공공 API
    - juso.go.kr 주소기반산업지원서비스의 검색/검증 API: 최신 도로명주소, 지번, 우편번호, 행정코드 반환.[^10][^4]
- 한국 특화 라이브러리
    - addresskr (Python): juso.go.kr API 응답을 객체화해 시/군/구, 법정동, 도로명, 상세주소 등 필드로 바로 활용.[^2]
- 국제/범용 라이브러리
    - libpostal: 전세계 주소 파싱·정규화용 C 라이브러리, 기계학습 기반으로 학습된 주소 모델 제공.[^16][^11][^3][^5]
    - postal (DeGAUSS 등 래퍼): libpostal 기반 주소 파싱/정규화 파이프라인 삽입용.[^15]


### 2.3 LLM 스택

- 오픈 LLM 모델
    - Qwen, Llama 계열 등 오픈웨이트 모델을 로컬 GPU 서버나 온프레미스에 배포.[^1][^13]
    - 주소 보정 특화 연구 예: AddrLLM – Retrieval-Augmented LLM으로 주소 재작성 성능 개선.[^1]
- LLM Serving
    - vLLM, Text Generation Inference(TGI) 등 고성능 서빙 프레임워크.[^14][^13]
    - REST/gRPC API로 사내 서비스·C\# 클라이언트에서 호출 가능.
- 워크플로·에이전트
    - Python 기반 LLM 파이프라인/에이전트 프레임워크(LangChain, LlamaIndex 등)로 “주소 정제 에이전트” 구성.[^7][^14]


### 2.4 프런트엔드·운영

- 관리 UI
    - React + TypeScript or Blazor(C\#)로 주소 정제 결과 리스트, 수동 검수, 로그 시각화 화면 구현.
- 백오피스 기능
    - 정제 룰 관리(블랙리스트/화이트리스트), API 키 관리(juso, 자체 LLM), 배치 작업 스케줄링 화면.
- 모니터링·로그
    - Prometheus + Grafana: API Latency, LLM 호출 비율, 실패율 모니터링.[^14]
    - ELK / OpenSearch: 주소 입력 패턴·에러 로그 분석.

***

## 3. 주소 정제 파이프라인 설계

### 3.1 입력·전처리 모듈

- 기능
    - 다양한 소스(CSV, Excel, DB, API)에서 주소 필드 추출.
    - 전처리 규칙: 제어문자 제거, 여러 줄 주소 합치기, 괄호 내 부가 정보 분리, 영문·한글 분리.[^9][^8]
- 구현 포인트
    - Python ETL 스크립트(예: pandas 기반) + C\# Import 모듈 조합.
    - 전처리 전/후 주소를 모두 저장하여 LLM 재학습·룰 튜닝에 사용.


### 3.2 1차 규칙/통계 기반 정제

- 단계 1: juso.go.kr API 호출
    - 검색 API를 통해 키워드 기반 매칭, 도로명주소/지번주소·우편번호·행정구역코드 확보.[^4][^10]
    - addresskr를 사용하면 도로명주소 응답을 그대로 Python 객체로 파싱해 필드 접근이 쉬워짐.[^2]
- 단계 2: libpostal 파싱
    - libpostal의 parse/expand 함수를 이용해 “도로명+번지+상세”를 토큰화 및 다양한 표기 변형 생성.[^11][^3][^5][^16]
    - 이를 이용해 fuzzy matching·중복 주소 탐지·영문 주소 정규화를 수행.[^15]


### 3.3 LLM 기반 고급 정제 (AddrLLM 방식 참조)

- 적용 시점
    - juso API 및 libpostal로도 매칭 실패하거나, 다중 후보가 나와 우선순위 결정이 어려운 레코드에만 LLM 호출.[^3][^1]
- 프롬프트 설계
    - 입력: 원본 주소, 전처리 주소, juso/libpostal 후보 목록, 내부 주소 마스터에서 조회된 후보 리스트.
    - 출력: 선택된 표준 주소, 신뢰도 점수, 선택 근거(설명) JSON.
- RAG 설계
    - 자체 구축한 주소 마스터(PostgreSQL/PostGIS, 시·군·구·읍·면·동·리·건물명 테이블)를 벡터/키워드 인덱싱 후, LLM이 검색 결과를 참조해 재작성.[^1][^14]
- 참고 연구
    - AddrLLM: 중국 JD LBS에서 2,000만 건 이상 주소 데이터로 학습, 비정상 주소 43.9% 정정, 기존 방법 대비 24.2% 개선 보고.[^1]


### 3.4 검증·품질 관리

- 규칙 기반 검증
    - 행정동코드–법정동코드 일관성, 시·구·동 계층 구조 검증.
    - 도로명코드–건물번호, 우편번호 일치 여부 확인.
- 공간 기반 검증
    - PostGIS에 행정구역 폴리곤을 저장하고, 지오코딩된 좌표가 해당 행정구역 안에 존재하는지 ST_Contains로 확인.
- LLM 결과 검증
    - LLM이 제안한 주소를 다시 juso API/libpostal로 역검증하여 치명적인 오류를 필터링.[^16][^4][^1]

***

## 4. 개발 단계별 추진 전략

### 4.1 1단계: 기본 정제 API (3개월 내외)

- 목표
    - juso.go.kr + libpostal + PostgreSQL 기반의 “비LLM 주소 정제 API” 완성.
- 주요 산출물
    - REST API: /normalize-address, /validate-address, /bulk-clean 등.
    - 기본 UI: CSV 업로드 → 정제 → 다운로드, 에러 로그 뷰.
- 기술 포인트
    - Python + FastAPI/Flask로 백엔드 구현, Docker 컨테이너로 패키징.[^5][^3][^14]


### 4.2 2단계: LLM·RAG 주소 보정 (3~4개월)

- 목표
    - 오픈 LLM을 연동한 “고급 정제 엔진” 추가, 이상치 처리 정확도 향상.
- 주요 작업
    - 내부 과거 주소 데이터(원본–정제 결과)를 few-shot/Instruction Tuning용 데이터셋으로 정제.[^17][^18]
    - LLM 서빙 환경(vLLM/TGI 등) 구성 및 사내 인프라 탑재.[^13][^14]
    - RAG 인덱스 구축: 행정구역, 도로명, 주요 건물·지명 DB 인덱싱.
- 참고 아키텍처
    - AddrLLM와 유사하게 “Supervised Fine-Tuning + RAG + Objective Alignment” 구조로 점진적 개선.[^1]


### 4.3 3단계: 제품화·SaaS화 (3개월+)

- 목표
    - CS 또는 Web 기반 상용 솔루션/SaaS로 패키징, 멀티 테넌트 운영 가능 구조.
- 기능
    - 테넌트별 API 키·쿼터 관리, 과금 로직(요청 건수, LLM 호출 비율) 도입.
    - 버전 관리: 주소 정제 룰셋·모델 버전별 A/B 테스트, 롤백 기능.
- 운영
    - CI/CD 파이프라인, 모니터링(성능/오류), SLA 대응 체계 구축.[^7][^14]

***

## 5. 스택 조합 예시 요약

| 계층 | 기술/제품 | 역할 |
| :-- | :-- | :-- |
| DB/공간 | PostgreSQL + PostGIS | 주소 마스터, 행정구역, 정제 로그, 좌표 검증 |
| 주소 파싱 | juso.go.kr API, addresskr | 한국 도로명/지번, 행정코드·우편번호 조회·파싱[^2][^4][^10] |
| 국제 파싱 | libpostal + postal | 다국어 주소 파싱·정규화, fuzzy matching[^11][^3][^15][^5][^16] |
| LLM | Qwen/Llama 오픈 LLM + vLLM/TGI | 이상치 주소 보정·재작성, RAG 기반 후보 선정[^1][^13][^14] |
| 백엔드 | Python(FastAPI) + C\# 서비스 | 정제 API, 배치, 사내 시스템 연계 |
| 프런트 | React/Blazor | 주소 정제 UI, 검수/로그 뷰어 |
| 인프라 | Docker, K8s(선택), Prometheus/Grafana | 배포·스케일링·모니터링[^3][^14] |


***

필요하다면,

- “PostgreSQL/PostGIS 주소 스키마 설계 예시(테이블·ERD)”
- “LLM 프롬프트/출력 JSON 스키마 예시”
- “도커 컴포즈 예시(yaml)와 배포 절차”

를 한국 주소(국가기반지도/행정동 코드 체계)를 기준으로 더 구체적으로 풀어서 작성해 줄 수 있다.
<span style="display:none">[^19][^20]</span>

<div align="center">⁂</div>

[^1]: https://arxiv.org/html/2411.13584v1

[^2]: https://pypi.org/project/addresskr/

[^3]: https://senzing.com/what-is-libpostal/

[^4]: https://business.juso.go.kr/addrlink/openApi/searchApi.do

[^5]: https://github.com/openvenues/libpostal

[^6]: https://scrapingant.com/blog/llm-powered-data-normalization-cleaning-scraped-data

[^7]: https://www.emergentmind.com/topics/llm-driven-automated-generation-pipeline

[^8]: https://latitude-blog.ghost.io/blog/ultimate-guide-to-preprocessing-pipelines-for-llms/

[^9]: https://www.databytego.com/p/aillm-series-building-a-smarter-data-510

[^10]: https://business.juso.go.kr/addrlink/openApi/apiExprn.do

[^11]: https://www.mapzen.com/blog/inside-libpostal/

[^12]: https://velog.io/@kjw9684/명함-데이터-주소처리

[^13]: https://decodo.com/glossary/llm-data-pipeline

[^14]: https://mirascope.com/blog/llm-pipeline

[^15]: https://degauss.org/postal/

[^16]: https://github.com/openvenues/libpostal/blob/master/README.md

[^17]: https://aclanthology.org/2025.emnlp-industry.6.pdf

[^18]: https://machinelearning.apple.com/research/polynorm

[^19]: https://huggingface.co/learn/llm-course/chapter6/4

[^20]: https://github.com/skysign/KoreaAddressAPI

