# SEWS — ICU 패혈증 조기 경보 시스템

PhysioNet 2019 ICU 시계열로 **24시간 관찰 → 6시간 후 패혈증 발생을 예측**하고, 보정된 확률과 SHAP 근거를 FastAPI·Streamlit으로 제공하는 End-to-End 임상 DSS.

> 폴더만 `BackEnd` / `FrontEnd`로 나누면 **데이터 파이프라인·학습·평가·MLOps가 갈 곳이 없습니다.** 이 저장소는 모노레포입니다.

## 문서

| 파일 | 내용 |
| --- | --- |
| [docs/프로젝트 소개.md](docs/프로젝트%20소개.md) | 원본 PBL 기획서 |
| [docs/팀프로젝트_초반세팅.md](docs/팀프로젝트_초반세팅.md) | 1주차 해야 할 일, Git, 폴더 역할 |
| [docs/팀프로젝트_초반세팅.html](docs/팀프로젝트_초반세팅.html) | 위 문서의 HTML 버전 |

## 디렉터리

```
api/          FastAPI 추론 서버
dashboard/    Streamlit 대시보드 (모델 직접 로드 금지)
src/          전처리·특징·학습·평가
data/         원본/중간/처리 데이터 (Git 제외)
models/       학습된 가중치 (Git 제외)
configs/      하이퍼파라미터·경로·임계값
docker/       Compose·Dockerfile
docs/         기획·계약·리포트
notebooks/    EDA만. 파이프라인 로직은 src/로 옮긴다
tests/        단위·계약 테스트
scripts/      다운로드·원클릭 실행 헬퍼
```

## 빠른 시작 (세팅 후)

1. DUA 동의 후 PhysioNet 2019 데이터를 `data/raw/`에 둔다.
2. Python 3.11 + 가상환경.
3. `docker compose up` (Phase 4 이후).

팀 규칙·브랜치·1주차 체크리스트는 `docs/팀프로젝트_초반세팅.md`를 본다.
