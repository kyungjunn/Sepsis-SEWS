# ICU 패혈증 조기 경보 Data Specification

CODESEY · DATA DESIGN REVIEW  
Project Definition Canvas의 Input을 수집·학습·평가 가능한 데이터 명세로 구체화한다.

> **실측 반영 개정 (2026-09-17).** 규모·결측률·양성 비율·시간 구조·품질 검사는 공개 학습 파일 40,336개를 직접 집계한 값이다. 근거: `docs/physionet-actual-profile.json`, `docs/physionet-data-1-3-study.md`. 원본 경로는 `physionet-data/physionet.org/files/challenge-2019/1.0.0/training`. 이 문서의 컬럼명·창 길이·분할·Feature 채택은 팀 계약이다.

| 항목 | 기입 |
| --- | --- |
| 팀명 | 중증예상센터 |
| 과제명 | ICU 패혈증 조기 경보 시스템 (SEWS) |
| 작성자 · 작성일 | 김경준 · 김승현 · 한다현 · 한승민 / 초안 2026-09-14, 실측 개정 2026-09-17 |
| 데이터 버전 | `sews-physionet2019-v0.1` |
| **AI Task** | **Classification** (드롭다운 한 개. 복합 Task 아님) |
| 예측 · 판단 시점 | ICU 시각 `t` = `ICULOS`에서 `[max(1, t−23), t]`만 보고, 원본 `SepsisLabel[t]`를 이진 분류한다. 양성은 공식 발생 시각 `t_sepsis`보다 최대 6시간 앞선 구간부터 시작한다. |

| AI TASK | 관측 단위 | 예측 대상 | 핵심 평가 |
| --- | --- | --- | --- |
| 이진 분류 (공식 6h-shift `SepsisLabel`) | 환자 × 1시간 | `SepsisLabel` ∈ {0,1} | AUPRC · Utility · Brier · AUROC |

**Classification인 이유.** 타깃이 다음 시간의 연속값이 아니라 0/1이다. 대시보드 신호등은 보정 확률을 0.50 / 0.75로 자른 분류 결과다. 24h 창은 입력 구조일 뿐 Forecasting이 아니다.

고르지 않음: Regression, Forecasting, Object Detection, Recommendation, Optimization, Generation, 복합 Task.

작성 원칙: 모델이 시각 `t`에서 실제로 쓸 수 있는 과거·현재만 Feature다. 원본 `SepsisLabel`을 재생성하거나 SOFA로 덮어쓰지 않는다.

---

## 실측으로 바뀐 계약

| 초안 | 실측 후 계약 |
| --- | --- |
| “t 이후 6시간 이내 Sepsis-3 발생” | 학습 타깃은 원본 `SepsisLabel`. `t ≥ t_sepsis−6`부터 1이고 **발생 후에도 1 유지**. 양성 행 전부가 “앞으로 6시간 안에 새로 발생”은 아님 |
| 시간 행 “약 250만+, 공개만 EDA에서 집계” | 공개 학습 **1,552,210행** (A 790,215 + B 761,995) |
| 양성률 문헌 근사 | 환자 2,932/40,336 (**7.2690%**), 시간 행 27,916 (**1.7985%**) |
| “성인 ICU만” | setA 최소 **18.11세**, setB 최소 **14세**. 소아 일반화 불가라고만 적지 말고 실제 범위를 적는다 |
| `EtCO2` 선택 Feature | setA **100% 결측**. Baseline Feature **제외** |
| Baseline에 표준 SOFA 6요소 필수 | GCS·승압제·소변량·PaO2 없음. Baseline은 **선택 A: SOFA 없이** 원본+24h 변화 Feature. PartialSOFA는 별도 실험 |
| 랩 결측을 “중~고”로만 표기 | 아래 표의 setA/setB **행 단위 결측률**을 쓴다. 행 결측 ≠ 환자 미시행 |
| T6 “Sepsis-3 라벨링” | 라벨은 원본 41번째 컬럼. 학습 시 재계산하지 않음 |

---

## 1. 목적과 예측 정의

ICU 시각 `t`까지 수집된 활력징후·검사값·인구통계와 최근 최대 24시간 변화량으로 PhysioNet 공식 `SepsisLabel`을 이진 분류하고, 임상 패혈증 발생 시점보다 최대 6시간 빠른 위험 확률 `p(SepsisLabel=1 | x_{≤t})`를 동적 경보(normal / warning / alert)의 입력으로 제공한다.

예측은 진단을 대신하지 않는다. ICU 의료진이 확인이 필요한 환자를 먼저 살피도록 돕는다.

### 관측 단위

| 단계 | 실제 의미 | 예시 |
| --- | --- | --- |
| 파일 1개 | ICU 환자 기록 1건 | `p005863.psv` |
| 행 1개 | 해당 환자의 특정 ICU 시간 1개 | `ICULOS=10` |
| 열 1개 | 그 시간의 측정값 또는 환자 정보 | `HR=80`, `Temp=37.3` |
| 학습 샘플 1개 | `(patient_id, t)` | `[max(1, t−23), t]` → `SepsisLabel[t]` |
| 추론 요청 1건 | `/predict` = 현재 창 | 최대 24행 × 원본 40변수 |

- 시간대: 이미 1시간 그리드. 그 시간에 측정 없으면 `NaN`이지 0이 아님
- 기본 키: **`patient_id + ICULOS`**
- `patient_id`: 파일명 스템. 파일 안 컬럼이 아님
- `hospital_set`: 상위 폴더 setA/setB에서 부여
- 분할 단위는 행이 아니라 **환자 ID**

#### 실제 파일에서 확인한 시간 구조

| 검사 항목 | setA | setB | 해석 |
| --- | ---: | ---: | --- |
| 파일 수 | 20,336 | 20,000 | 파일 1개 = 환자 기록 1건 |
| 전체 행 수 | 790,215 | 761,995 | 합계 **1,552,210**시간 행 |
| 환자당 행 수 최소 | 8 | 8 | 원 대회 포함 조건 |
| 중앙값 | 39h | 38h | 평균보다 긴 입원 영향이 적음 |
| 평균 | 38.858h | 38.100h | 환자당 약 38시간 |
| 95백분위 | 58h | 58h | 환자 95%가 이 이하 |
| 최대 | 336h | 336h | 14일. 원 대회가 이 길이로 절단 |
| 중복 `ICULOS` | 0 | 0 | 같은 환자·같은 시간 중복 없음 |
| 빠진 시간 칸 | 0 | 0 | 파일 안에서 `ICULOS`가 1씩 연속 |
| 역순 환자 | 0 | 0 | 시간 순서 정상 |
| 라벨 1→0 복귀 | 0 | 0 | 한 번 양성이면 체류 끝까지 1 |

최소 기록은 8시간, 관측 창은 24시간이다. ICU 입실 초기에는 창이 차지 않는다.

**짧은 창 규칙**

1. `t < 24`여도 예측 샘플로 사용한다.
2. 실제로 존재하는 입실 이후 데이터만 사용한다.
3. 부족한 과거는 `NaN`과 결측 표시로 남긴다.
4. 미래 행을 가져와 채우지 않는다.

### Target 정의

| 항목 | 내용 |
| --- | --- |
| 변수명 | `SepsisLabel` |
| 의미 | 공식 6시간 시프트 라벨. 패혈증 환자에서 발생 6시간 전부터 1, 발생 후에도 1 |
| 자료형 | int `{0, 1}` |
| 생성 | 원본 41번째 컬럼. **학습 시 재계산하지 않는다** |
| 담당 | PhysioNet Challenge 2019 (Singer et al. Sepsis-3 규칙을 대회 측이 적용) |
| 결측 | A/B 모두 0 |

```text
패혈증 발생 시각 = t_sepsis
현재 행의 시간 = t

if t >= t_sepsis - 6:
    SepsisLabel = 1
else:
    SepsisLabel = 0
```

**포함**

- 비패혈증 환자: 모든 시간 0
- 패혈증 환자: `t < t_sepsis − 6` → 0, `t ≥ t_sepsis − 6` → **1 (체류 끝까지 유지)**

**제외 · 해석 주의**

- 원본에 없는 것: 혈액배양 시각, IV 항생제, 승압제, GCS, 소변량, PaO2. 따라서 **우리가 SOFA·Sepsis-3로 라벨을 다시 만들 수 없다.**
- 발생 이후 시간축의 1은 “조기경보”가 아니라 “이미 패혈증”이다.
  - **학습 기본:** 공식 라벨 그대로 (Utility와 정합).
  - **학습 대안:** 첫 양성 이후 행은 Train에서만 제외. 채택 시 이 문서와 `configs/`를 같이 올린다.
- `alert_level`은 Target이 아니다. 추론 후처리 (`p<0.50` normal, `0.50≤p<0.75` warning, `p≥0.75` alert).

Sepsis-3 원 정의는 라벨 검증·설명용이다. Feature가 아니고, 원본 라벨을 대체하지 않는다.

1. `t_suspicion` = IV 항생제와 혈액배양 중 더 이른 시각. 항생제 선행 시 24h 내 배양, 배양 선행 시 72h 내 항생제. 항생제 72시간 연속.
2. `t_SOFA` = 24h 안에 SOFA **+2**.
3. `t_suspicion − 24 ≤ t_SOFA ≤ t_suspicion + 12` 일 때만 패혈증, `t_sepsis = min(t_suspicion, t_SOFA)`.

공개 파일에는 위 계산에 필요한 변수가 빠져 있다.

### 예측 시점과 Horizon

| 항목 | 값 |
| --- | --- |
| 기준 시점 t | `ICULOS` (ICU 입실 후 시간, 1h) |
| Observation window | **24h** `[t−23, t]`. `t<24`이면 입실 이후만. **오른쪽(미래) 패딩 금지** |
| Prediction horizon | 공식 라벨이 이미 **6h 선행 시프트**. 모델은 `SepsisLabel[t]`를 맞힌다 |
| 갱신 주기 | 1시간마다 재추론 |
| 라벨이 1인 시각 | `t ≥ t_sepsis−6` (발생 이후 포함) |
| t에서 사용 금지 | t 이후 바이탈/랩, t 이후 점수, `SepsisLabel`, 퇴원 후 정보 |

```text
ICULOS ----[ t-23 ........ t ]----
           Feature: t 이하만
           Target: SepsisLabel[t]
           t 이후 측정값을 보면 Leakage
```

같은 수치라도 **현재값보다 변화**가 중요하다. 같은 `HR=105`라도 평소 빈맥과 급상승은 다르다. 그래서 last / mean / max / delta / slope / missingness를 만든다.

---

## 2. 데이터 출처와 수집 범위

데이터셋: **PhysioNet/Computing in Cardiology Challenge 2019** v1.0.0  
DOI: `10.13026/v64v-d857`  
주제: 임상 데이터로 패혈증을 조기에 예측하기

공개 학습 데이터는 서로 다른 두 병원 시스템의 ICU 기록이다.

- setA: Beth Israel Deaconess Medical Center 계열
- setB: Emory University Hospital 계열
- 병원 C: 대회 숨김 평가용. 공개 training 폴더에 없음

각 파일은 파이프(`|`)로 열을 구분한 `.psv`다. 한 시간에 여러 번 측정된 값은 원 대회 제작 과정에서 시간 단위로 요약됐다. 우리가 가진 파일은 원시 모니터 신호가 아니라 **이미 1시간 단위로 가공된 임상 표**다.

| 데이터 영역 | 출처·소유자 | 수집 항목 | 기간·주기 | 확보 상태 | 권한·주의사항 |
| --- | --- | --- | --- | --- | --- |
| ICU EHR 시계열 | PhysioNet/CinC Challenge 2019 v1.0.0, 공개 병원 A/B | `.psv` 40,336개. 활력징후 8 · 검사 26 · 인구/관리 6 · 라벨 1 | 환자당 8~336시간, 1시간 단위 | setA 20,336명/790,215행, setB 20,000명/761,995행. 스키마 불일치 0 | 출처 표기, 이용조건 준수, 재식별·원본 재배포 금지. Git에 psv 없음 |
| 숨김 병원 C | 동일 Challenge | 동일 스키마 예상, 문헌상 24,819명 | — | **미확보. 사용 안 함** | 외부 일반화는 setB hold-out으로 대체 |
| 패혈증 정의 | Singer et al., JAMA 2016 | 감염 의심, SOFA +2 규칙 | 정적 | 문헌 확보 | 설명·검증용. 라벨 재생성 금지 |
| Utility 채점 | PhysioNet 공식 코드 | 시간별 효용 | 정적 | 공식 자료 확보 | 평가 전용. Feature 금지 |
| 실시간 병원 EMR | 없음 | — | — | 미확보 | 재현 데모. 실제 병원 연결 아님. API는 학습과 같은 40변수 JSON만 |
| 달력·날씨·이벤트 | 없음 | — | — | 해당 없음 | 절대시각이 없어 공휴일 Feature 불가 |

### setA와 setB를 같은 데이터로 보면 안 되는 이유

| 변수 | setA 결측률 | setB 결측률 | 차이 |
| --- | ---: | ---: | --- |
| `DBP` | 48.126% | 13.945% | 이완기 혈압 기록 관행이 크게 다름 |
| `Resp` | 9.777% | 21.139% | setB에서 호흡수 누락이 더 많음 |
| `EtCO2` | **100.000%** | 92.436% | setA에는 값이 하나도 없음 |
| `BaseExcess` | 89.575% | 99.769% | setB에서는 거의 측정되지 않음 |
| `Glucose` | 87.768% | 77.840% | setB가 혈당 기록은 더 많음 |
| `Lactate` | 96.565% | 98.123% | 양쪽 모두 매우 드문 검사 |
| 환자 양성률 | 8.8021% | 5.7100% | 라벨 밀도도 병원마다 다름 |

결측 여부 자체가 검사 필요 판단을 담을 수 있다. 병원별 습관을 모델이 외우면 다른 병원에서 성능이 떨어진다.

- setA: Train · Validation
- setB: 다른 병원 최종 Test. 보고 반복적으로 모델을 고치지 않음
- `hospital_set`은 기본 Feature에서 제외

---

## 3. 주요 데이터 스키마

역할: Key / Feature / Target / meta(학습 입력 금지).  
예측 시점 `t`에서 이용 가능해야 Feature다.  
결측률은 **전처리 전 원본 시간 행 기준**이다. 예: setA `Lactate` 96.565%는 “환자 96.565%가 한 번도 안 했다”가 아니라 **그 시간 행이 비어 있다**는 뜻이다.

원본은 **41개 컬럼**이다. 활력징후 8 + 검사 26 + 인구통계·관리 6 + Target 1. `patient_id`와 `hospital_set`은 파일명·경로에서 추가한다.

### 3.1 식별 · 시간 · 타깃

| 변수명 | 역할 | 자료형 | 정의·단위 | 예측 시점 이용 | 결측·범위 | 필수 |
| --- | --- | --- | --- | --- | --- | --- |
| `patient_id` | Key | str | 파일명 스템. 분할 키. MRN 아님 | 항상 | 결측 0. Feature 제외 | 필수 |
| `ICULOS` | Key / Feature | int | ICU 입실 후 시간 h, 환자 내 1씩 연속 | 항상 (= t) | 결측 0. 8~336 | 필수 |
| `hospital_set` | meta | {A,B} | 상위 폴더 | 항상 | 결측 0 | 필수(분할). 모델 입력 기본 제외 |
| `HospAdmTime` | Feature | float | 병원 입원→ICU 입실 시차 h. 대개 음수 | 정적 | A 8행(0.001%), B 0% | 권장 |
| `SepsisLabel` | Target | int | 공식 6h-shift 0/1 | **예측 시점 불가** | 결측 0. Feature 금지 | 필수 |
| `sepsis_onset_hour` | meta | int/null | 환자 첫 양성 `ICULOS` | 집계 후 | 비패혈증은 null | Utility·차트. 입력 금지 |
| `sepsis_patient` | meta | int | encounter에 양성 1회 이상 | 집계 후 | — | 입력 금지 |
| `split` | meta | str | Train/Val/Test | 분할 후 | — | 입력 금지 |
| `data_version` | meta | str | manifest | 생성 후 | — | 입력 금지 |

### 3.2 활력징후 (원본 8)

모두 float. 이용 조건 `관측 시각 ≤ t`. 범위 밖은 삭제하지 않고 NaN + `{var}_out_of_range`.

| 변수명 | 정의·단위 | A 결측 | B 결측 | 유효범위 | Baseline |
| --- | --- | ---: | ---: | --- | --- |
| `HR` | 심박수 bpm | 7.743% | 12.101% | 20–220 | **핵심** |
| `O2Sat` | 맥박산소 % | 12.032% | 14.128% | 50–100 | **핵심** |
| `Temp` | 체온 °C | 66.224% | 66.099% | 30–43 | **핵심**. last + hours_since |
| `SBP` | 수축기 혈압 mmHg | 15.211% | 13.919% | 50–250 | **핵심**. 부분 qSOFA 후보 |
| `MAP` | 평균동맥압 mmHg | 10.232% | 14.752% | 40–180 | **핵심** |
| `DBP` | 이완기 혈압 mmHg | 48.126% | 13.945% | 20–150 | 권장. 병원 차이 주의 |
| `Resp` | 호흡수 /min | 9.777% | 21.139% | 4–60 | **핵심**. 부분 qSOFA 후보 |
| `EtCO2` | 호기말 CO₂ mmHg | **100.000%** | 92.436% | — | **기본 제외**. setA 값 없음 |

### 3.3 검사 (원본 26)

이용: 마지막 관측 시각 ≤ t. 대부분 드물게 측정되므로 시간 행 결측이 정상이다. 2% 결측 목표를 두지 않는다. 값과 함께 last / hours_since / measured / missing_rate를 만든다.

| 변수명 | 정의·단위 | A 결측 | B 결측 | Baseline |
| --- | --- | ---: | ---: | --- |
| `Lactate` | 젖산 mg/dL | 96.565% | 98.123% | **핵심**. 측정 여부 자체가 신호일 수 있음 |
| `WBC` | 백혈구 10³/µL | 92.490% | 94.738% | **핵심** |
| `Creatinine` | 신장 기능 mg/dL | 93.358% | 94.471% | **핵심** |
| `Bilirubin_total` | 총 빌리루빈 mg/dL | 98.773% | 98.235% | **핵심**. 결측 매우 큼 |
| `Platelets` | 혈소판 10³/µL | 93.483% | 94.657% | **핵심** |
| `FiO2` | 흡입산소 분율 | 85.807% | 97.741% | **핵심**. %>1이면 /100해서 0–1 |
| `Glucose` | 혈당 mg/dL | 87.768% | 77.840% | 권장. B가 더 자주 기록 |
| `BUN` | 혈중 요소질소 mg/dL | 91.841% | 94.476% | 권장 |
| `Potassium` | 칼륨 mmol/L | 89.138% | 92.298% | 권장. 1.5–8.0 |
| `Hct` | 적혈구 비율 % | 88.224% | 94.176% | 권장 |
| `Hgb` | 헤모글로빈 g/dL | 91.164% | 94.125% | 권장 |
| `HCO3` | 중탄산염 mmol/L | 91.949% | 99.815% | 선택. B 거의 없음 |
| `BaseExcess` | 산-염기 치우침 mmol/L | 89.575% | 99.769% | 선택. B 거의 없음 |
| `pH` | 동맥혈 pH | 88.533% | 97.775% | 권장. 6.8–7.8 |
| `PaCO2` | 동맥혈 CO₂ mmHg | 91.232% | 97.767% | 선택 |
| `SaO2` | 동맥혈 산소포화 % | 95.044% | 98.110% | 선택. `O2Sat`과 혼동 금지 |
| `Calcium` | 칼슘 mg/dL | 95.024% | 93.174% | 선택 |
| `Chloride` | 염화물 mmol/L | 91.676% | 99.385% | 선택. B 거의 없음 |
| `Magnesium` | 마그네슘 mmol/dL | 92.220% | 95.214% | 선택 |
| `Phosphate` | 인산염 mg/dL | 94.951% | 97.060% | 선택 |
| `PTT` | 응고시간 sec | 95.152% | 99.030% | 선택 |
| `AST` | 간·근육 효소 IU/L | 98.504% | 98.246% | 선택 |
| `Alkalinephos` | 간·담도·뼈 효소 IU/L | 98.541% | 98.240% | 선택 |
| `Bilirubin_direct` | 직접 빌리루빈 mg/dL | 99.850% | 99.763% | 선택. missingness만 |
| `TroponinI` | 심근 손상 ng/mL | 99.878% | 98.187% | 선택. missingness만 |
| `Fibrinogen` | 응고 단백질 mg/dL | 99.237% | 99.447% | 선택. missingness만 |
| PaO2 | — | 원본에 없음 | 원본에 없음 | 사용 불가. 호흡 SOFA 불가 |

### 3.4 인구통계 · 관리정보 (원본 6)

| 변수명 | 역할 | 자료형 | 정의·단위 | A 결측 | B 결측 | 주의 |
| --- | --- | --- | --- | ---: | ---: | --- |
| `Age` | Feature | float | 세. 90+는 100 캡 | 0% | 0% | A 18.11~89 (중앙 64.67), B **14~100** (중앙 62). 성인만이라고 쓰지 않음 |
| `Gender` | Feature | int | 0 여 / 1 남 | 0% | 0% | A 여 8,502 / 남 11,834. B 여 9,268 / 남 10,732 |
| `Unit1` | meta | {0,1}/NaN | MICU | 48.868% | 29.632% | 둘 다 NaN일 수 있음. 병원 프로토콜 누수. **기본 모델 제외** |
| `Unit2` | meta | {0,1}/NaN | SICU | 48.868% | 29.632% | 위와 동일 |
| `HospAdmTime` | Feature | float | 입원→ICU 시차 h | 0.001% | 0% | 대개 음수 |
| `ICULOS` | Key/Feature | int | ICU 경과 h | 0% | 0% | 환자별 시간 키 |

### 3.5 웹앱 양식용 대표 스키마

칸이 제한되면 이 행을 먼저 넣는다.

| 변수명 | 역할 | 자료형 | 정의·단위 | 예측 시점 이용 | 결측·유효범위 |
| --- | --- | --- | --- | --- | --- |
| `patient_id` | Key | str | 파일명 기반 기록 ID | 항상 | 결측 0, Feature 제외 |
| `ICULOS` | Key/Feature | int | ICU 입실 후 시간 h | 항상 | 결측 0, 연속 |
| `HR` | Feature | float | 심박수 bpm | t까지 | A 7.743%, B 12.101% |
| `O2Sat` | Feature | float | 산소포화도 % | t까지 | A 12.032%, B 14.128% |
| `Temp` | Feature | float | 체온 °C | t까지 | A 66.224%, B 66.099% |
| `SBP` | Feature | float | 수축기 혈압 mmHg | t까지 | A 15.211%, B 13.919% |
| `MAP` | Feature | float | 평균동맥압 mmHg | t까지 | A 10.232%, B 14.752% |
| `Resp` | Feature | float | 호흡수 /min | t까지 | A 9.777%, B 21.139% |
| `Lactate` | Feature | float | 젖산 mg/dL | 결과가 t까지 나온 경우 | A 96.565%, B 98.123% |
| `WBC` | Feature | float | 백혈구 10³/µL | t까지 | A 92.490%, B 94.738% |
| `Creatinine` | Feature | float | 신장 기능 mg/dL | t까지 | A 93.358%, B 94.471% |
| `Bilirubin_total` | Feature | float | 총 빌리루빈 mg/dL | t까지 | A 98.773%, B 98.235% |
| `Platelets` | Feature | float | 혈소판 10³/µL | t까지 | A 93.483%, B 94.657% |
| `Age` | Feature | float | 나이 | 입원 시 고정 | 결측 0. A 18.11~89, B 14~100 |
| `Gender` | Feature | int | 0 여, 1 남 | 입원 시 고정 | 결측 0 |
| `SepsisLabel` | Target | int | 공식 6h-shift 0/1 | **예측 시점 이용 불가** | 결측 0. Feature 금지 |

### 3.6 파생 Feature (24h Sliding Window)

기획 요구 **50개 이상**. Baseline(선택 A)은 원본 변수와 시간 변화만으로 충족한다. 모든 통계의 우측 끝 = t.

**창을 씌우는 핵심 원변수 (12):** `HR, O2Sat, Temp, SBP, MAP, Resp, Lactate, WBC, Creatinine, Bilirubin_total, Platelets, FiO2`

`EtCO2`는 창 변수에서 뺀다. `DBP`·`Glucose`·`BUN`·`Potassium`·`Hct`·`Hgb`는 같은 패턴을 권장으로 추가할 수 있다.

| 패턴 | 정의 | 핵심 12개 기준 | Baseline |
| --- | --- | ---: | --- |
| `{var}_last` | 창 안 마지막 관측 | 12 | 필수 |
| `{var}_mean_24h` | 창 평균 | 12 | 필수 |
| `{var}_std_24h` | 창 표준편차. 관측 2 미만이면 NaN | 12 | 권장 |
| `{var}_min_24h`, `{var}_max_24h` | 창 최저·최고 | 24 | 권장 |
| `{var}_slope_24h` | 시간 대비 선형 기울기 | 12 | 권장 |
| `{var}_delta_6h` | last − 6h 전 last | 12 | 권장 |
| `{var}_measured` | 해당 시간 실측 여부 | 12 | 필수 |
| `{var}_missing_rate_24h` | 창 결측 비율 0–1 | 12 | 필수 |
| `{var}_hours_since` | 마지막 실측 후 경과 h. 한 번도 없으면 큰 값+플래그 | 12 | 권장 |
| `{var}_count_24h` | 창 안 실측 횟수 | 12 | 선택 |
| `Age`, `Gender`, `HospAdmTime`, `ICULOS` | 정적·시간 | 4 | 필수 |
| `shock_index_last` | `HR_last / SBP_last`. SBP=0이면 NaN | 1 | 선택 |

필수만으로도 `12×(last+mean+missing_rate+measured) + 4 = 52`개다. slope·delta·hours_since를 더하면 80을 넘는다.

XGBoost Baseline은 이 요약 벡터를 입력한다. LSTM은 24시간 순서를 그대로 넣을 수 있으나, 첫 모델은 XGBoost다.

### 3.7 SOFA · qSOFA 정책

공개 40변수만으로 표준 SOFA 6요소와 완전한 qSOFA를 계산할 수 없다. Challenge 다른 팀도 표준 SOFA를 재현하지 못했고, 쓰더라도 `PartialSOFA` / `pseudo-SOFA` / `SOFA-related`라고 불렀다.

빠진 입력: GCS, 승압제, 소변량, PaO2, 배양·항생제 시각.

| 점수 영역 | 사용 가능한 값 | 한계 |
| --- | --- | --- |
| 호흡 | `O2Sat`, `FiO2` | PaO2/FiO2 불가 |
| 응고 | `Platelets` | 계산 가능 |
| 간 | `Bilirubin_total` | 가능하나 결측 약 98% |
| 심혈관 | `MAP` | 승압제 없어 2~4점 불가 |
| 신경 | 없음 | GCS 없어 계산 불가 |
| 신장 | `Creatinine` | 소변량 없음 |
| qSOFA | `SBP`, `Resp` | 의식 항목 없음. 최대 2항목 |

**선택 A — Baseline (채택)**  
SOFA 계열 Feature를 쓰지 않는다. 원본 변수의 last / mean / min / max / slope / missingness를 모델이 직접 학습한다.

**선택 B — 별도 실험**  
4항목 PartialSOFA만 보조 Feature로 넣는다. 이름은 `SOFA`가 아니라 `partial_sofa`다.

```text
partial_sofa =
    platelet_score          # 0–4
  + bilirubin_score         # 0–4
  + creatinine_score        # 0–4, 소변량 기준 없음
  + map_score               # MAP<70이면 1, 그 이상 불가

partial_sofa_delta_24h =
    현재 partial_sofa - 이전 24시간 partial_sofa 최저값

partial_sofa_deterioration_24h =
    1 if partial_sofa_delta_24h >= 2 else 0
```

선택 B 규칙:

1. 구성 항목이 하나도 없으면 합계도 결측. 빠진 항목을 0으로 채워 “정상”과 “측정 불가”를 섞지 않는다.
2. Forward-fill은 같은 환자의 **과거만**.
3. `partial_sofa +2`는 공식 Sepsis-3의 `SOFA +2`가 아니다.
4. 원본 `SepsisLabel`을 수정하는 데 쓰지 않는다.
5. AUPRC·Utility·Brier가 좋아지지 않으면 제거한다.
6. 대시보드에는 “표준 SOFA”가 아니라 “공개 데이터 4항목 부분 점수”라고 표시한다.

부분 qSOFA 이진 Feature(`Resp ≥ 22`, `SBP ≤ 100`)도 선택 B에만 넣는다. 의식 항목이 없어 3점 만점 qSOFA라고 부르지 않는다.

---

## 4. 데이터 규모와 분포

집계 원본: `docs/physionet-actual-profile.json`. 원본을 수정하지 않고 읽기만 했다.

### 규모

| 항목 | 값 |
| --- | --- |
| 공개 환자 기록 | **40,336** (A 20,336 + B 20,000) |
| 공개 시간 행 | **1,552,210** (A 790,215 + B 761,995) |
| 숨김 테스트 | 문헌상 24,819 — 미사용 |
| 원본 변수 | 40 + 라벨 1. 전 파일 컬럼 수 동일, 스키마 불일치 0 |
| 파일 | 환자당 `.psv` 1개 |
| 포함 조건 (원 대회, 이미 적용됨) | 체류 ≥8h, `t_sepsis`가 입실 후 4h 미만이면 제외, 2주 초과는 2주 절단 |
| 공간 | 미국 병원 2곳 공개. 절대시각·주소 없음 |

### Target · 클래스 분포 (실측)

| 항목 | setA | setB | 합계 |
| --- | ---: | ---: | ---: |
| 환자 기록 | 20,336 | 20,000 | 40,336 |
| 패혈증 환자 | 1,790 | 1,142 | 2,932 |
| 환자 단위 양성률 | 8.8021% | 5.7100% | **7.2690%** |
| 시간 행 | 790,215 | 761,995 | 1,552,210 |
| 양성 시간 행 | 17,136 | 10,780 | 27,916 |
| 시간 행 양성률 | 2.1685% | 1.4147% | **1.7985%** |
| 첫 양성 `ICULOS` 중앙값 | 29.5h | 28.5h | — |
| 첫 양성 최소 / 최대 | 1 / 331 | 1 / 331 | — |

환자 단위 양성률과 행 단위 양성률은 다르다. 양성 행이 약 1.8%뿐이라 **클래스 불균형**이 심하다. 전부 0으로 말해도 Accuracy는 높아 보이므로 Accuracy만 평가하지 않는다.

→ **AUPRC · Utility · Brier/ECE**. AUROC는 보조.  
→ Class weight / Focal Loss. SMOTE는 시계열 의존을 깨서 기본 아님.

목표 성능 (기획서): AUROC ≥0.82, AUPRC ≥0.40, Brier ≤0.15.

### 집단 · 기간별 대표성

| 축 | 실측 | 대응 |
| --- | --- | --- |
| 병원 | A vs B 라벨 비율·결측 패턴이 다름 | Train/Val=A, Test=B 1회 |
| 연령 | A 18.11~89, B 14~100. 90+ → 100 | “성인만”이라고 쓰지 않음. 소아 일반화는 주장하지 않음 |
| 성별 | A 남 11,834 / 여 8,502. B 남 10,732 / 여 9,268 | 층화 보고 |
| 체류 | 중앙 38~39h, 최대 336h, 입실 초 창 부족 | `ICULOS` 구간 성능. 짧은 창 허용 |
| 검사 밀도 | 바이탈은 상대적으로 자주, 랩은 드묾. EtCO2는 A에서 전무 | missingness Feature. EtCO2 기본 제외 |
| 병원 C | 미확보 | setB로 병원 이동 흉내 |

### 추가 수집 계획

원본 추가 없음. 부족한 것은 파생으로 채운다.

- 결측 과다: 값 대신 측정 여부·경과시간
- GCS/승압제/PaO2/소변량 없음: 표준 SOFA 계산 안 함
- 양성 희소: 환자 단위 유지. 시간 undersample은 **Train만**

목표: 공개 40,336명 파이프라인 통과, Feature 컬럼 ≥50 (선택 A).

---

## 5. 데이터 품질 기준

담당: 데이터 엔지니어. 로그: `data/interim/quality_report.json` (요약만 `docs/`).

원본 40,336파일 1차 검사 결과 (전처리 전):

| 항목 | setA | setB |
| --- | ---: | ---: |
| 스키마 불일치 | 0 | 0 |
| 중복 시각 | 0 | 0 |
| 시간 칸 누락 | 0 | 0 |
| 비단조 시간 | 0 | 0 |
| 라벨 1→0 | 0 | 0 |

| 품질 항목 | 검사 규칙 | 허용 기준 | 문제 시 처리 |
| --- | --- | --- | --- |
| **유일성** | `patient_id + ICULOS` 한 행. 파일 1개=환자 1명. setA∩setB=∅ | 중복 0 | 중복 시각은 median 재집계. ID 충돌은 중단 |
| **완전성** | 헤더 40+1. `SepsisLabel` NaN 없음. 체류 ≥8h | 키·타깃 결측 0%. 랩 결측은 2% 목표 아님 | 스키마/타깃 실패 파일 → `rejected.csv`. 양성 환자를 결측 때문에 버리지 않음 |
| **유효성** | §3 물리 범위. `Gender`∈{0,1}. 라벨∈{0,1} | 범위 밖 비율 기록 | 범위 밖 → NaN + out_of_range. **행 삭제 금지** |
| **시간 연속성** | 환자 내 `ICULOS` 정수, 간격 1, 단조 | 위반 0 (원본 실측 0) | 정렬. 빈 시간은 호출 0이 아니라 원본이 체류 구간만 제공 |
| **병원 일관성** | set별 결측·라벨·Age 분포 | A/B 차이를 보고로 남김 | 병합 학습은 EDA 후에만. 기본은 A→B |
| **신선도** | 학습은 정적 파일. 서비스는 요청 JSON의 마지막 `ICULOS`=t | 허용 지연 1h | 초과 시 `/health` stale. 대시보드 회색. 학습 Fallback 없음 |
| 대치 누수 | Imputer/Scaler는 Train 환자만 fit | Test fit 0건 | 단위 테스트 |
| 분할·미래 누수 | ID 교집합 0, Feature 시각 ≤ t | 0 | 파이프라인 실패 |
| Git | raw/processed/models 미추적 | parquet/psv 0 | pre-commit |

결측 처리 비교(T4): 바이탈 짧은 공백 Forward-fill vs 유지+indicator vs 선형보간. **KNN 기본 아님.** 양방향 보간 금지. 선택은 EDA 근거를 `docs/`에 남긴다. Fill은 같은 환자의 과거만.

**주의:** Lactate·HR·체온의 큰 값을 단순 이상치로 지우면 실제 패혈증 피크를 지운다. 물리 불가능(HR 20 미만 등)과 임상 극단값을 구분한다.

---

## 6. Train · Validation · Test 분할

무작위 행 분할하지 않는다. 공개 데이터에 절대시각이 없어 달력식 time split도 못 한다. **환자 Group + 병원 공간 분할.** 시드 **42**.

```text
TRAIN                    VALIDATION           TEST (봉인)
setA 환자 80%            setA 환자 20%        setB 환자 100%
≈16,269명                ≈4,067명             20,000명 (다른 병원)
가중치·Imputer·창 통계   HP, 조기종료,         최종 1회
                         Calibration, 임계값   AUROC/AUPRC/Brier/Utility
```

Group 5-Fold는 **Train(A) 안**에서만. Val은 폴드 hold-out과 최종 20% 고정 중 하나를 `splits/`에 못 박는다.

| 집합 | 역할 | 선택 기준 | 금지 |
| --- | --- | --- | --- |
| Train | 모델, Imputer, Scaler | — | Test 통계 사용 |
| Val | Platt/Isotonic, 임계값 0.50/0.75 재조정 후보 | AUPRC 우선, Utility, Brier/ECE. AUROC 보조 | Val을 Test처럼 반복 확정 |
| Test | 공표 | 기획 목표치 | 튜닝. MLflow 이름은 `final_`만 |

배포와의 관계: 운영 시 새 환자는 학습에 없는 ID + 다른 기록 관행. 환자 hold-out + setB가 그 상황을 모사한다.

대안(문서화 후): A+B를 70/15/15로 섞고 병원 이동은 stress만. 기본은 A-train / B-test.

### 별도 Stress Test

| 시나리오 | 구성 | 보는 것 |
| --- | --- | --- |
| 희소 양성 / 전부 음성 | 패혈증만, 비패혈증만 | FPR → Alert Fatigue |
| 입실 초기 | `ICULOS < 12` | 짧은 창 (원본 최소 8h) |
| 장기 체류 | `ICULOS > 72` | 드리프트 |
| 랩 공백 | Lactate·WBC 24h 결측 | missingness가 버티는지 |
| 센서 이상 | HR/MAP 범위 밖 상위 | 이상치 플래그 |
| 병원 이동 | A→B | 일반화 (기본 Test와 동일) |
| Utility 창 | t_sepsis−12 ~ +3 | 너무 이른 경보 패널티 |
| 발생 이후 시간 | 첫 양성 이후만 | “이미 환자” 성능 vs 조기경보 |
| 연령 | setB `Age < 18` | 초안 “성인만”과 실제 분포 차이 |

---

## 7. Data Leakage 방지 규칙

학습 시작 전 전부 통과.

- 모든 Feature가 예측 시점 t에 존재한다 (`ICULOS ≤ t`). Lag·Rolling도 t 이전만.
- 전처리 통계(평균, 분위, Imputer, Scaler, Calibrator, Encoding)는 Train 환자에서만 fit한다. 전체 기간 StandardScaler 금지.
- 같은 환자·같은 `.psv`가 Train/Val/Test에 중복되지 않는다.
- 시계열 미래가 과거 Feature에 안 들어간다. ffill·LOCF는 과거→현재만. `limit_direction='forward'`.
- Target 이후 변수(`SepsisLabel`, 발생 이후로만 생기는 파생, 퇴원 후 통계)를 Feature로 쓰지 않는다.
- Test(setB) 점수로 모델을 반복 선택하지 않는다.
- `Unit1/Unit2`·`hospital_set`은 기본 제외 (프로토콜·병원 습관 암기).
- 대시보드는 parquet/모델을 직접 읽지 않는다. 학습·서빙은 같은 `src/preprocess`.
- PartialSOFA를 쓰더라도 라벨을 재생성하지 않는다.

### 프로젝트별 위험과 차단

| 위험 변수·단계 | 가능한 누수 | 검사·차단 |
| --- | --- | --- |
| `SepsisLabel` 컬럼 | 타깃 직접 입력 | Feature 화이트리스트. 테스트가 라벨명 탐지 |
| 양방향 interpolate | 미래 랩이 현재를 채움 | 미래값 주입 후 Feature 불변 테스트 |
| `train_test_split` 행 단위 | 한 환자 양분 | Group split만. ID 교집합 assert |
| 체류 전체 평균 | 퇴원 후·미래 통계 | 창 우측 끝 = t |
| SOFA로 라벨 재생성 | 미래 검사로 +2, 공식과 불일치 | 학습 타깃은 원본 고정. Baseline은 SOFA 미사용 |
| 짧은 창을 미래로 채움 | t<24인데 t 이후 행 사용 | 왼쪽만 관측, 오른쪽 패딩 금지 |
| setB로 튜닝 | Test 재사용 | `final_` 메트릭만 |
| Utility 버그 | 미래 라벨로 임계값 | 공식 스크립트 숫자 대조 |
| SHAP이 raw psv | 전처리 불일치 | API만 호출 |

---

## 8. 전처리와 Feature Pipeline

코드: `src/preprocess` → `src/features`. 산출: `data/raw` → `data/interim` → `data/processed`.

```text
원본 psv 보존 → 스키마·중복 검증 → 범위 정제·단위 통일 → 결측플래그
       → 24h Lag/Rolling Feature → 환자 Group 분할 → Train 기준 Impute/Scale
       → (별도 실험) PartialSOFA
```

| 단계 | 처리 내용 | 산출물·검증 |
| --- | --- | --- |
| 01 수집 | DUA 후 setA/B. 현재 원본 `physionet-data/.../training`. 파이프라인은 `data/raw/training_setA\|B`. SHA256·파일 수 | `docs/data-manifest.md`. Git에 psv 없음 |
| 02 검증 | 헤더, 행≥8, ICULOS 단조, 라벨 {0,1}, ID 교집합 없음 | `rejected.csv`, setA vs setB 결측·양성 보고. 1차 실측은 품질 위반 0 |
| 03 정제 | 물리 범위 밖 NaN+플래그. FiO2 %→분율. 중복 시각 median | 제외 건수·사유. 양성 환자 미삭제 |
| 04 변환 | 재샘플 없음. 바이탈 짧은 공백은 과거만 ffill. 랩 LOCF + `{var}_hours_since`. **표준 SOFA 계산 없음** | Join 없음(단일 테이블) |
| 05 Feature | `(patient_id, t)` 창 24. last/mean/std/min/max/slope/missing_rate/delta/measured. 컬럼≥50. 왼쪽만 패딩. EtCO2 제외 | `features.parquet`, `feature_list.json`. 미래 참조 단위테스트 |
| 06 분할 | 시드 42, 환자 ID. Train 컬럼에 split. 5-Fold는 A 안 | `splits/{train,val,test}_ids.txt` |
| 07 변환(학습) | Imputer·Scaler fit=Train | 같은 Pipeline을 Val/Test/FastAPI에 적용 |
| 08 버전 | `sews-physionet2019-v0.1` + commit + seed + window + n_rows | `manifest.json` |
| 실험 B | PartialSOFA 4항목 + deterioration. 라벨 불변 | A/B 메트릭 비교 후 채택 여부 결정 |

### 재현성

| 기록 | 방법 |
| --- | --- |
| 코드 | Git SHA. 노트북에 전처리 200줄 금지 |
| 파라미터 | `configs/default.yaml` (seed 42, window 24, horizon 6, warning 0.50, alert 0.75) |
| 난수 | `src/common` 한곳 |
| 환경 | Python 3.11 → `requirements-ml.txt` + Docker |
| 실험 | MLflow: data_version, commit, 메트릭 |
| 실측 프로파일 | `docs/physionet-actual-profile.json` |

### 학습–서비스 일치

- FastAPI가 `src/preprocess`·`src/features`를 동일 import.
- 입력 JSON = 원본 40변수 창. 서버가 창 통계를 다시 계산.
- Scaler/Imputer는 Train에서 저장한 `.pkl`만.
- `dashboard/`는 `/predict`, `/explain`만. 모델 로드 금지.
- 계약: `docs/api-contract.md`.
- 대시보드가 점수를 보여 줄 때 표준 SOFA라고 쓰지 않는다.

---

## 9. 개인정보 · 라이선스 · 보안

### 개인정보 · 민감정보

포함: EHR 건강정보. PhysioNet 비식별화(Age 90+ 캡, 직접식별자 없음).  
최소수집: 우리 쪽 추가 수집 없음.  
가명 `patient_id`는 파일 스템이지 병원 MRN이 아니다. 그래도 공개 저장소에 안 넣는다.  
재식별·환자 단위 외부 공유·원본 GitHub 업로드 금지.  
원본 `.psv`, 처리 `.parquet`, 환자별 예측 결과는 GitHub에 올리지 않는다. 코드·스키마·집계 통계만 공유한다.

### 라이선스 · 이용 조건

- Reyna et al., PhysioNet Challenge 2019 v1.0.0. DOI `10.13026/v64v-d857`
- Reyna et al., Crit Care Med 2020;48:210–217
- 파일 라이선스 CC-BY-4.0 공지이나 **DUA가 우선**. 교육 사용, 출처 표기
- 원본 재배포(GitHub Releases, 공개 드라이브) 금지
- 코드·리포트는 private 저장소
- 제출 전 이용조건·인용을 다시 확인한다

### 접근권한 · 보관

| 항목 | 규칙 |
| --- | --- |
| 사용자 | 팀 4인 + 지도 범위. PhysioNet 계정은 개인 |
| 저장 | 로컬/팀 공유 `SEWS/data` 및 `physionet-data/`. Git 제외 |
| 암호화 | 팀 권한만. `.env`·계정 커밋 금지 |
| 보존 | 학기 종료 후 DUA에 따라 원본 삭제 또는 자격 기간만 |
| 모델 | `models/` 로컬. 공개 repo 기본 제외 |

### 외부 API · 데이터 위험

학습 시 외부 데이터 API 없음. 운영은 대시보드→FastAPI만.  
스키마 변경은 계약 버전으로. 필드 추가 시 구버전 거절.  
`/health`가 모델 로드 실패를 반환. 대시보드는 Mock JSON으로 UI 유지.

---

## 10. 데이터 버전과 산출물

### 권장 폴더·파일

- `physionet-data/` — 내려받은 원본 (현재 확보 위치)
- `data/raw/` — 파이프라인이 읽는 원본 psv (변경 금지)
- `data/interim/` — 검증 통과·거절 로그
- `data/processed/` — Feature parquet
- `data/processed/splits/` — Train·Val·Test ID
- `docs/data-specification.md` — 이 명세
- `docs/physionet-actual-profile.json` — 실측 집계
- `configs/default.yaml` — seed·창·임계값

### 버전 기록

| 필드 | v0.1 |
| --- | --- |
| 데이터 버전 | `sews-physionet2019-v0.1` |
| 수집 기간 | PhysioNet 공개 A/B. 다운로드 일자 기입 |
| 생성일 | 파이프라인 실행일 |
| 원본 Snapshot·Hash | 파일 수 40,336 + SHA256 |
| 전처리 Commit | `git rev-parse HEAD` |
| 시드 / 창 / horizon | 42 / 24h / 6h |
| 행·열·결측·제외 | `manifest.json`. 원본 행 1,552,210 |
| 명세 근거 | 2026-09-17 실측 프로파일 |

창 길이·결측 전략·Baseline Feature 집합이 바뀌면 `v0.2`. 모델만 바뀌면 데이터 버전 유지. PartialSOFA 실험 채택 시 Feature 목록을 올리고 버전을 올린다.

### 산출물 목록

| 산출 | 경로 |
| --- | --- |
| raw | `data/raw/training_setA`, `training_setB` |
| validated | `data/interim/` + `rejected.csv` |
| features | `data/processed/features.parquet`, `feature_list.json` |
| splits | `data/processed/splits/{train,val,test}_ids.txt` |
| data_spec | 이 문서 |
| 실측 프로파일 | `docs/physionet-actual-profile.json` |
| 품질 보고서 | `docs/eda-quality-report.md` |
| 계약 | `docs/data-contract.md`, `docs/api-contract.md` |

### 완료 기준

- 다른 팀원이 이 문서와 commit만으로 동일 parquet·동일 split ID를 재생성한다.
- 모든 Feature·Target의 의미와 사용 가능 시각을 설명할 수 있다.
- `SepsisLabel`이 발생 이후에도 1이라는 점을 학습 범위 문서에 명시한다.
- Test(setB)가 배포 후 만날 다른 병원 환자를 모사한다. 같은 환자 재등장 없음.
- 모델 점수를 data_version + git commit까지 추적한다.
- Leakage 테스트 통과. 원본이 Git에 없다.
- Baseline은 SOFA 없이 ≥50 Feature. PartialSOFA는 실험 기록이 있다.

3주: EDA 실측 + 이 명세 확정. 6주: 전처리와 parquet.

---

## 모델이 배우는 것

입력: 현재까지 관측된 환자 상태와 최근 변화  
정답: 그 시간의 원본 `SepsisLabel`

패혈증 환자가 모두 같은 수치를 보이지 않으므로 여러 조건의 복합 패턴을 본다. 예: 심박수 증가, MAP 감소, 호흡수 증가, 산소포화도 감소, Creatinine 상승, 최근 Lactate 검사 시행, 그 변화가 몇 시간 지속.

학습 과정: 40,336명 시간별 기록 → 각 시간마다 최근 최대 24시간 특징 추출 → 특징과 `SepsisLabel`의 관계 학습 → 새 환자의 같은 특징 입력 → `SepsisLabel=1` 확률 출력.

SOFA는 사람이 정한 점수 규칙이다. 이 모델의 Baseline은 데이터에서 여러 수치의 관계와 변화 패턴을 직접 학습한다.

---

## 웹앱 붙여넣기 요약

| 필드 | 한 줄 |
| --- | --- |
| AI Task | **Classification** |
| 데이터 목적 | ICU 시각 t까지 24h 변화량으로 공식 `SepsisLabel`을 이진 분류하고, 발생보다 최대 6시간 빠른 위험 확률을 제공한다 |
| 관측 단위 | 파일=환자 기록 1건, 행=환자×1시간. 학습 샘플=`(patient_id, t)` + 최대 24h 창. 키 `patient_id + ICULOS` |
| Target | `SepsisLabel` 0/1. `t ≥ t_sepsis−6`부터 1, 발생 이후도 1. 원본 라벨. 재생성 금지 |
| 예측 시점 / Horizon | t=`ICULOS`, 창 24h, 공식 6h-shift, 갱신 1h, t 이후 측정 금지 |
| 출처 | PhysioNet 2019 v1.0.0. A 20,336/790,215행 + B 20,000/761,995행. 합 40,336/1,552,210 |
| 분할 | Group(환자), seed 42. Train/Val=setA, Test=setB 봉인 |
| 파이프라인 | 수집→검증→정제→24h Feature(≥50, EtCO2·SOFA 제외)→분할→Train fit. PartialSOFA는 실험 |
