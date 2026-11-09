"""저축 씨앗 | Streamlit 교육용 목표 저축 앱
실행: pip install -r requirements.txt && streamlit run app.py
배포: GitHub에 이 파일과 requirements.txt 업로드 → Streamlit Community Cloud
→ 저장소와 app.py 선택 → Deploy. 배포 URL을 앱의 QR 탭에 입력합니다.
선택: Cloud의 Settings > Secrets에서 PUBLIC_APP_URL = "https://....streamlit.app"
을 지정하면 QR 주소를 자동 입력합니다. API 키/계좌/로그인 정보는 필요 없습니다.
중요: 기록은 세션 메모리에만 존재합니다. 새로고침·재접속·서버 재시작 시
사라질 수 있으므로 JSON 백업을 내려받으세요. QR은 앱 주소만 공유하며,
개인 기록은 공유하거나 동기화하지 않습니다. 실제 금융 거래는 하지 않습니다.
"""
from __future__ import annotations

import calendar
import html
import io
import json
import uuid
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

import pandas as pd
import qrcode
import streamlit as st

MAX_MONEY = 1_000_000_000
LESSONS = [
    {"id": "goal", "title": "1. 목표를 숫자로 바꾸기", "body": "'돈을 모으자' 대신 '90일 안에 자전거 비용 30만 원 모으기'처럼 금액과 기한을 정해 보세요. 필요한 하루 저축액은 남은 금액을 남은 일수로 나누면 됩니다. 빠듯하면 기간을 늘리거나 목표를 조정할 수 있어요.", "question": "실행 계획을 세우기 가장 좋은 목표는?", "options": ["언젠가 많이 모으기", "90일 안에 자전거 비용 30만 원 모으기", "친구보다 많이 모으기"], "answer": 1, "explain": "금액·기한·목적이 구체적이면 행동으로 옮기고 진행 상황을 확인하기 쉬워요."},
    {"id": "first", "title": "2. 선저축과 예산", "body": "선저축은 수입이 들어오면 계획한 금액을 먼저 따로 두고 나머지로 소비하는 방법입니다. 식비·교통비 등 꼭 필요한 지출을 먼저 확인하고, 지속 가능한 금액을 정하세요. 특정 저축 비율이 모든 사람에게 정답인 것은 아니에요.", "question": "수입이 불규칙할 때 더 합리적인 방법은?", "options": ["생활비를 무시하고 무조건 절반 저축", "필수 지출과 수입 변동을 고려해 저축액 조정", "저축하려고 매달 대출받기"], "answer": 1, "explain": "무리해서 시작하기보다 실제 생활에 맞는 금액으로 꾸준히 이어가는 것이 중요해요."},
    {"id": "needs", "title": "3. 필요와 욕구, 기회비용", "body": "필요는 생활에 꼭 필요한 지출, 욕구는 있으면 좋지만 미룰 수 있는 지출입니다. 상황에 따라 구분은 달라져요. 기회비용은 어떤 선택을 하느라 포기한 가장 가치 있는 다른 선택입니다. 소비를 모두 나쁘게 보기보다 나의 우선순위를 생각해 보세요.", "question": "간식 5천 원 대신 저축하기로 했다면 포기한 간식의 만족은?", "options": ["공짜 이자", "기회비용", "원금 보장"], "answer": 1, "explain": "선택에는 포기하는 가치가 있어요. 소비와 저축의 장단점을 함께 비교해 보세요."},
    {"id": "interest", "title": "4. 단리와 복리", "body": "단리는 원금에만 이자가 붙고, 복리는 이전 이자를 포함한 잔액에 이자가 붙습니다. 같은 조건이라면 복리는 시간이 길수록 누적 효과가 커져요. 실제 상품은 세금·수수료·납입 시점·계약상 이자 계산 방식에 따라 결과가 달라집니다.", "question": "복리를 가장 잘 설명하는 것은?", "options": ["원금에만 이자가 붙는다", "항상 원금의 두 배가 된다", "이전 이자를 포함한 잔액에도 이자가 붙는다"], "answer": 2, "explain": "복리는 이자에도 이자가 붙는 구조입니다. 높은 수익이 보장된다는 의미는 아니에요."},
    {"id": "buffer", "title": "5. 비상금과 안전한 습관", "body": "예상치 못한 지출에 대비하는 비상금은 목표 저축과 별도로 생각할 수 있어요. 쉽게 꺼낼 수 있는지, 손실 위험이 있는지 확인하세요. '고수익 보장'이나 계좌·비밀번호를 요구하는 낯선 링크는 경계하세요. 이 앱에는 계좌번호 등 민감정보를 적지 마세요.", "question": "비상금의 중요한 조건은?", "options": ["필요할 때 쉽게 쓸 수 있는 유동성과 안전성", "언제나 가장 높은 수익률", "친구에게 비밀번호 공유"], "answer": 0, "explain": "비상금은 급할 때 쓸 수 있어야 해요. 필요한 규모는 생활비와 소득 안정성에 따라 달라집니다."},
]
MISSIONS = {
    "pause": ("소비 전 10분 멈추기", "사고 싶은 물건 하나를 고르고, 필요한 이유와 미뤄도 되는 이유를 생각해 보세요."),
    "budget": ("오늘의 필수 지출 점검", "오늘 꼭 필요한 지출 하나와 줄일 수 있는 지출 하나를 구분해 보세요."),
    "plan": ("다음 저축 계획 세우기", "언제, 얼마를 저축할지 구체적으로 정해 보세요. 실천 전에는 입금으로 기록하지 마세요."),
}


def fresh_data():
    return {"version": 1, "goal": None, "entries": [], "learned": [], "missions": {}}


def money(value):
    return f"{value:,.0f}원"


def balance(entries):
    return sum(e["amount"] if e["kind"] == "저축" else -e["amount"] for e in entries)


def valid_url(raw):
    try:
        p = urlsplit(raw.strip())
        return bool(p.scheme == "https" and p.hostname and "." in p.hostname and not p.username and not p.password and not p.fragment and not p.query)
    except ValueError:
        return False


def simulate(initial, monthly, annual_rate, months):
    """월말 납입, 연 명목금리/12, 세전. 단리: 누적 납입원금에만 이자."""
    principal = float(initial)
    simple = float(initial)
    compound = float(initial)
    rows = [{"개월": 0, "납입 원금": principal, "단리 잔액": simple, "복리 잔액": compound}]
    r = annual_rate / 100 / 12
    for month in range(1, months + 1):
        simple += principal * r + monthly
        compound = compound * (1 + r) + monthly
        principal += monthly
        rows.append({"개월": month, "납입 원금": principal, "단리 잔액": simple, "복리 잔액": compound})
    return rows


def validate_backup(obj):
    """엄격하게 검증하고 허용한 필드만 새 객체로 복원합니다."""
    if not isinstance(obj, dict) or type(obj.get("version")) is not int or obj["version"] != 1:
        raise ValueError("지원하는 버전의 JSON 백업이 아닙니다.")
    out = fresh_data()
    g = obj.get("goal")
    if g is not None:
        if not isinstance(g, dict) or not isinstance(g.get("name"), str) or not 1 <= len(g["name"].strip()) <= 60:
            raise ValueError("목표 이름을 확인하세요.")
        if type(g.get("target")) is not int or not 1 <= g["target"] <= MAX_MONEY:
            raise ValueError("목표 금액을 확인하세요.")
        due = date.fromisoformat(g["due"])
        out["goal"] = {"name": g["name"].strip(), "target": g["target"], "due": due.isoformat()}
    entries = obj.get("entries", [])
    if not isinstance(entries, list) or len(entries) > 3000:
        raise ValueError("거래 내역은 최대 3,000건입니다.")
    ids = set()
    for e in entries:
        if not isinstance(e, dict) or e.get("kind") not in ("저축", "사용"):
            raise ValueError("거래 종류가 올바르지 않습니다.")
        amount = e.get("amount")
        if type(amount) is not int or not 1 <= amount <= MAX_MONEY:
            raise ValueError("거래 금액이 올바르지 않습니다.")
        day = date.fromisoformat(e["date"])
        if day > date.today():
            raise ValueError("미래 날짜의 거래는 복원할 수 없습니다.")
        note = e.get("note", "")
        if not isinstance(note, str) or len(note) > 120:
            raise ValueError("메모는 120자 이내여야 합니다.")
        eid = e.get("id")
        if not isinstance(eid, str) or not 1 <= len(eid) <= 64 or eid in ids:
            raise ValueError("거래 ID가 잘못되었거나 중복되었습니다.")
        ids.add(eid)
        out["entries"].append({"id": eid, "date": day.isoformat(), "kind": e["kind"], "amount": amount, "note": note})
    if balance(out["entries"]) < 0:
        raise ValueError("전체 잔액은 음수가 될 수 없습니다.")
    learned = obj.get("learned", [])
    allowed = {x["id"] for x in LESSONS}
    if not isinstance(learned, list) or any(not isinstance(x, str) or x not in allowed for x in learned):
        raise ValueError("학습 기록이 올바르지 않습니다.")
    out["learned"] = sorted(set(learned))
    missions = obj.get("missions", {})
    if not isinstance(missions, dict) or len(missions) > 3660:
        raise ValueError("미션 기록이 올바르지 않습니다.")
    for day, values in missions.items():
        parsed = date.fromisoformat(day)
        if parsed > date.today() or not isinstance(values, list) or any(not isinstance(x, str) or x not in MISSIONS for x in values):
            raise ValueError("미션 날짜 또는 내용이 올바르지 않습니다.")
        out["missions"][parsed.isoformat()] = sorted(set(values))
    return out


CHALLENGES = [
    {"id":"pause", "title":"편의점의 유혹", "scene":"이번 주 자유 예산은 12,000원. 교통비로 8,000원이 필요해요. 지금 6,000원짜리 간식 세트를 사고 싶다면?", "options":["교통비를 빼놓고 남은 4,000원 안에서 고른다", "일단 사고 부족한 돈은 나중에 생각한다", "무조건 아무것도 먹지 않는다"], "answer":0, "why":"필수 지출을 먼저 확보한 뒤 남은 예산 안에서 고르는 것이 지속 가능해요. 모든 소비를 참는 게 정답은 아닙니다."},
    {"id":"first", "title":"용돈 입금! 첫 번째 선택", "scene":"용돈 50,000원이 들어왔어요. 이번 주 필수 지출은 30,000원, 목표 저축은 10,000원입니다. 가장 실행 가능한 방법은?", "options":["50,000원 전부 저축하고 생활비는 빌린다", "필수 지출을 확보하고 10,000원을 먼저 따로 둔다", "다 쓴 뒤 남으면 저축한다"], "answer":1, "why":"필수 지출을 확보한 뒤 계획한 저축을 먼저 분리하면 소비에 휩쓸리는 것을 줄일 수 있어요."},
    {"id":"interest", "title":"이자에도 이자가?", "scene":"원금 100,000원, 연 10%로 2년간 추가 납입 없이 굴립니다. 매년 복리이고 세금이 없다면 마지막 잔액은?", "options":["110,000원", "120,000원", "121,000원"], "answer":2, "why":"첫해 110,000원에 다시 10%가 붙어 121,000원이 됩니다. 연 10%는 계산용 가정이지 실제 상품 추천이 아닙니다."},
    {"id":"buffer", "title":"갑자기 고장 난 자전거", "scene":"다음 달에도 꼭 쓸 비상금이에요. 어디에 둘지 결정할 때 가장 먼저 확인할 조건은?", "options":["가장 화려한 광고", "필요할 때 꺼낼 수 있는지와 손실 위험", "친구가 추천했는지"], "answer":1, "why":"비상금은 유동성과 안전성이 중요해요. 높은 수익률만 보고 결정하지 마세요."},
    {"id":"needs", "title":"오늘 살까, 목표를 지킬까", "scene":"옷 구매를 미루고 여행비를 모으기로 했어요. 이 선택으로 포기한 옷의 만족은 무엇일까요?", "options":["기회비용", "복리", "수수료"], "answer":0, "why":"기회비용은 선택하면서 포기한 가장 가치 있는 대안이에요. 소비를 나쁘다고 단정하기보다 우선순위를 비교해요."},
]


def product_projection(initial, monthly, rate, months, method, tax):
    """Educational month-end model; deposit maturity is not a bank quote."""
    r = rate / 100 / 12
    principal = float(initial)
    total = float(initial)
    accrued = 0.0
    rows = [{"개월":0, "납입 원금":principal, "세후 예상 잔액":principal}]
    for m in range(1, months + 1):
        if method == "월복리":
            total *= 1 + r
        elif method == "연복리":
            accrued += total * r
            if m % 12 == 0:
                total += accrued
                accrued = 0.0
        else:
            accrued += principal * r
        principal += monthly
        total += monthly
        gross = total + accrued
        net = principal + (gross - principal) * (1 - tax / 100)
        rows.append({"개월":m, "납입 원금":principal, "세후 예상 잔액":net})
    return rows


def required_monthly(target, initial, months, rate, method, tax):
    if initial >= target:
        return 0
    low, high = 0, target
    while low < high:
        mid = (low + high) // 2
        final = product_projection(initial, mid, rate, months, method, tax)[-1]["세후 예상 잔액"]
        if final >= target:
            high = mid
        else:
            low = mid + 1
    return low


def main():
    st.set_page_config(page_title="저축 씨앗", page_icon="🌱", layout="centered")
    st.markdown("""<style>
    .stApp{background:#f5f8f6;color:#17352b}
    .block-container{max-width:920px;padding-top:2rem}
    h1,h2,h3{color:#14532d!important}
    div[data-testid="stMetric"]{background:white;border:1px solid #d2e8db;border-radius:16px;padding:16px}
    .arena{background:#080e18;color:#fff;border-radius:22px;padding:48px 24px;margin:16px 0;text-align:center;border-top:28px solid #030609;border-bottom:28px solid #030609}
    .arena h2{color:#baf8cc!important;font-size:30px}
    .arena p{font-size:20px;line-height:1.7}
    </style>""", unsafe_allow_html=True)
    if "seed_data" not in st.session_state:
        st.session_state.seed_data = fresh_data()
    data = st.session_state.seed_data
    today = date.today()
    with st.sidebar:
        st.title("🌱 저축 씨앗")
        page = st.radio("무엇을 할까요?", ["🏠 내 저축", "🎮 오늘의 도전", "🧮 목표 설계 · 이자", "⚙️ 목표 설정", "📱 QR · 데이터"], key="navigation")
        st.caption("목표 확인 → 계획 설계 → 저축 → 도전")
        st.caption("은행 연결 없는 교육용 앱 · 실제 이체 없음")
    st.caption("☰ 모바일에서는 왼쪽 위 메뉴를 열어 화면을 바꿀 수 있어요.")
    st.warning("현재 기록은 세션에만 저장됩니다. 재접속 전 ‘QR · 데이터’에서 JSON 백업을 저장하세요.")
    if st.session_state.pop("flash", False):
        st.success("반영했습니다.")
    g = data["goal"]
    current = balance(data["entries"])

    if page == "🏠 내 저축":
        st.title("지금 얼마나 가까워졌을까?")
        if not g:
            st.info("처음이라면 메뉴의 ‘목표 설정’에서 이름·금액·기한을 정하세요. 그다음 ‘목표 설계 · 이자’가 필요한 월 저축액을 계산해 드립니다.")
        else:
            st.subheader(g["name"])
            a,b = st.columns(2)
            a.metric("모은 돈", money(current)); b.metric("남은 목표", money(max(g["target"]-current,0)))
            st.progress(min(current/g["target"],1.0),text=f"달성률 {current/g['target']*100:.1f}% · 목표일 {g['due']}")
            if current >= g["target"]:
                st.success("🏆 목표 달성! 다음 목표를 설정해도 기록은 유지됩니다.")
        st.subheader("이체했나요? 금액만 빠르게 기록하세요")
        st.caption("은행 이체와 중복 작업을 줄이기 위한 간편 입력입니다. 이체 확인·자동 수집 기능은 없으며 기록은 자기 보고입니다.")
        with st.form("quick",clear_on_submit=True):
            amount=st.number_input("금액 (원)",min_value=1,max_value=MAX_MONEY,value=10000,step=1000)
            kind=st.radio("종류",["저축","사용"],horizontal=True)
            if st.form_submit_button("오늘 기록하기",type="primary"):
                if len(data["entries"])>=3000: st.error("기록은 최대 3,000건입니다.")
                elif kind=="사용" and amount>current: st.error("잔액보다 많이 사용할 수 없습니다.")
                else:
                    data["entries"].append({"id":uuid.uuid4().hex,"date":today.isoformat(),"kind":kind,"amount":int(amount),"note":"간편 기록"})
                    st.session_state.flash=True; st.rerun()
        with st.expander("내역 확인 · 잘못된 기록 삭제"):
            if data["entries"]:
                frame=pd.DataFrame(data["entries"])
                st.dataframe(frame[["date","kind","amount","note"]].rename(columns={"date":"날짜","kind":"종류","amount":"금액(원)","note":"메모"}),hide_index=True,use_container_width=True)
                choices={e["id"]:f"{e['date']} {e['kind']} {money(e['amount'])}" for e in data["entries"]}
                selected=st.selectbox("삭제할 내역",list(choices),format_func=lambda x:choices[x])
                agreed=st.checkbox("선택한 내역을 삭제합니다")
                if st.button("내역 삭제",disabled=not agreed):
                    rest=[e for e in data["entries"] if e["id"]!=selected]
                    if balance(rest)<0: st.error("음수 잔액이 됩니다. 관련 사용 내역부터 삭제하세요.")
                    else: data["entries"]=rest; st.rerun()
            else: st.info("아직 기록이 없습니다.")
        st.info("🎮 지출 선택을 바꾸는 짧은 게임은 메뉴의 ‘오늘의 도전’에서 시작하세요. 정답으로 배지를 모읍니다.")

    elif page == "🎮 오늘의 도전":
        st.title("오늘의 도전")
        st.caption("시나리오를 읽고 정답을 맞혀야 보상 획득 · 클릭만으로 점수 없음 · 실제 행동/이체를 인증하는 기능은 아닙니다.")
        # Keep historical mission points separate; only verified quiz answers count here.
        score=len(data["learned"])*20
        stage="씨앗" if score<40 else "새싹" if score<80 else "나무"
        st.metric("도전 경험치",f"{score} XP",delta=f"현재 배지: {stage}",delta_color="off")
        remaining=[c for c in CHALLENGES if c["id"] not in data["learned"]]
        feedback=st.session_state.pop("challenge_feedback",None)
        if feedback:
            st.success(feedback)
            st.balloons()
        if not remaining:
            st.success("🏆 모든 도전 완료! 정답으로 배운 원리를 ‘목표 설계 · 이자’에서 직접 실험해 보세요.")
            with st.expander("획득한 지식 카드 다시 보기"):
                for c in CHALLENGES: st.write(f"**{c['title']}** — {c['why']}")
        else:
            challenge=remaining[0]
            cid=challenge["id"]
            st.progress(len(data["learned"])/5,text=f"클리어 {len(data['learned'])}/5")
            st.markdown(f'<div class="arena"><small>MISSION · 정답을 선택해 잠금을 해제하세요</small><h2>{html.escape(challenge["title"])}</h2><p>{html.escape(challenge["scene"])}</p></div>',unsafe_allow_html=True)
            with st.form("challenge_"+cid):
                selected=st.radio("나의 선택",range(3),format_func=lambda x:challenge["options"][x],index=None)
                submitted=st.form_submit_button("⚡ 정답 제출 · 보상 받기",type="primary",use_container_width=True)
                if submitted:
                    if selected is None: st.warning("먼저 답을 골라 주세요.")
                    elif selected!=challenge["answer"]: st.info("아직 클리어하지 못했어요. 필수 지출·지속 가능성·계산 조건을 다시 살펴보세요. 다시 도전할 수 있습니다.")
                    else:
                        if cid not in data["learned"]: data["learned"].append(cid)
                        st.session_state.challenge_feedback="🎉 클리어! +20 XP · "+challenge["why"]
                        st.rerun()
        st.caption("경험치는 학습 성취 표시이며 현금·금리 혜택과 무관합니다. 재시도 가능하며 실물 행동의 증명이 아닙니다.")

    elif page == "🧮 목표 설계 · 이자":
        st.title("내 목표, 매달 얼마면 될까?")
        st.caption("상품명이 아닌 이자 계산 구조를 비교합니다. 실제 상품의 약관·일수·납입일·우대 조건은 다를 수 있습니다.")
        target=st.number_input("얼마를 모을까요? (원)",min_value=1,max_value=MAX_MONEY,value=g["target"] if g else 1000000,step=10000)
        initial=st.number_input("지금 가진 시작 금액 (원)",min_value=0,max_value=MAX_MONEY,value=min(current,MAX_MONEY),step=10000)
        base=st.slider("기준 기간 (개월)",1,120,12)
        budget=st.number_input("생활비를 제외하고 매달 가능한 최대 저축액 (원)",min_value=0,max_value=MAX_MONEY,value=100000,step=10000)
        method=st.selectbox("이자 계산 방식",["단리","월복리","연복리"])
        rate=st.slider("가정 연 명목금리 (%)",0.0,15.0,3.0,0.1)
        tax=st.number_input("가정 이자 공제율 (%) — 실제 적용률 확인 후 입력",min_value=0.0,max_value=100.0,value=0.0,step=0.1)
        st.caption("공제율 기본값 0%는 법정 세율 안내가 아닌 실험용 입력입니다. 이자에만 만기 일괄 공제한다고 가정합니다.")
        st.subheader("속도는 다르게, 목표는 같게")
        periods=[max(1,base//2),base,min(240,base*2)]
        names=["🔥 빡세게 · 단기 집중","🌿 중간 · 균형","🐢 약하게 · 오래"]
        plans=[]
        for label,n in zip(names,periods):
            req=required_monthly(target,initial,n,rate,method,tax)
            plans.append({"모드":label,"기간(개월)":n,"필요 월 저축액(원)":req,"예산 대비":"가능" if req<=budget else "월 예산 초과"})
        st.dataframe(pd.DataFrame(plans),hide_index=True,use_container_width=True)
        st.caption("단기=기준 기간의 절반(내림·최소 1개월), 균형=기준 기간, 장기=두 배입니다. 1개월에서는 단기·균형 기간이 같을 수 있습니다. 추천은 입력 예산과 계산 결과 기준이며 재무 진단이 아닙니다.")
        feasible=next((n for n in range(1,241) if product_projection(initial,budget,rate,n,method,tax)[-1]["세후 예상 잔액"]>=target),None)
        if initial>=target: st.success("시작 금액만으로 이미 목표를 달성했습니다.")
        elif feasible: st.info(f"입력한 월 예산 {money(budget)}을 유지하면 약 {feasible}개월에 목표에 도달하는 계산입니다.")
        else: st.warning("현재 가정으로는 240개월 안에 목표에 도달하지 않습니다. 목표·예산·기간을 조정하세요. 금리를 무리하게 높이는 것은 해결책이 아닙니다.")
        pick=st.selectbox("그래프로 살펴볼 계획",range(3),format_func=lambda i:names[i])
        chosen=plans[pick]; n=chosen["기간(개월)"]; payment=chosen["필요 월 저축액(원)"]
        monthly=st.number_input("직접 바꿔보는 월 납입액 (원)",min_value=0,max_value=MAX_MONEY,value=payment,step=1000,key=f"payment_{pick}_{payment}")
        rows=product_projection(initial,monthly,rate,n,method,tax)
        end=rows[-1]
        a,b=st.columns(2)
        a.metric("예상 잔액",money(end["세후 예상 잔액"]))
        b.metric("이자 공제 후 이익",money(end["세후 예상 잔액"]-end["납입 원금"]))
        st.line_chart(pd.DataFrame(rows).set_index("개월"),color=["#64748b","#15803d"])
        with st.expander("예금·적금은 왜 같은 금리인데 다른가요?"):
            st.write("목돈 예치는 시작 금액을 넣고 월 납입을 0으로, 매월 적립은 시작 금액을 0으로 두고 비교하세요. 월말에 넣는 마지막 납입금에는 이자가 붙지 않아 납입 원금 전체에 표시 금리를 곱한 값과 달라집니다.")
            st.write("단리는 납입 원금에만 월 이자를 누적하고, 월복리는 이자를 매월 잔액에 반영합니다. 연복리는 월 이자를 별도로 쌓아 12개월마다 원금화하고 남은 기간 이자는 종료 시 정산합니다. 월 이율은 연 명목금리÷12이며 매월 말 납입합니다. 모든 계산은 고정금리·월 단위의 교육용 근사입니다.")
            st.write("일복리, 변동금리, 구간별 금리, 우대 조건, 실제 일수 계산, 중도해지 금리와 수수료는 아직 지원하지 않습니다. 계산 결과가 은행의 지급액이나 수익 보장은 아닙니다. 계산값은 저축 기록에 자동 반영되지 않습니다.")
        st.caption("작은 실험: 금리를 0%로 낮춰도 목표에 도달할 수 있을까요? 기간과 월 납입액 중 내가 조절할 수 있는 것을 먼저 바꿔 보세요.")

    elif page == "⚙️ 목표 설정":
        st.title("하나의 목표부터 시작해요")
        with st.form("goal_form"):
            name=st.text_input("무엇을 위해 모으나요?",value=g["name"] if g else "여행 경비",max_chars=60)
            target=st.number_input("목표 금액 (원)",1,MAX_MONEY,g["target"] if g else 1000000,step=10000)
            due=st.date_input("언제까지?",value=max(date.fromisoformat(g["due"]),today) if g else today+timedelta(days=365),min_value=today,max_value=date(today.year+20,12,31))
            if st.form_submit_button("목표 저장",type="primary"):
                if not name.strip(): st.error("목표 이름을 입력해 주세요.")
                else:
                    data["goal"]={"name":name.strip(),"target":int(target),"due":due.isoformat()}
                    st.session_state.flash=True; st.rerun()
        st.caption("목표를 변경해도 잔액·내역은 유지됩니다. ‘목표 설계 · 이자’의 기간은 직접 선택하는 비교용 기간이며 이 목표 날짜를 자동 변경하지 않습니다.")

    else:
        st.title("QR 접속 · 내 기록 보관")
        st.subheader("휴대폰으로 열기")
        try: default=str(st.secrets.get("PUBLIC_APP_URL",""))
        except Exception: default=""
        url=st.text_input("배포된 공개 HTTPS 주소",value=default,placeholder="https://내앱.streamlit.app")
        if url:
            if valid_url(url):
                buf=io.BytesIO(); qrcode.make(url.strip()).save(buf,format="PNG")
                st.image(buf.getvalue(),width=220)
                st.download_button("QR 다운로드",buf.getvalue(),"saving-seed-qr.png","image/png")
            else: st.error("로그인 정보·쿼리·프래그먼트 없는 HTTPS 주소를 입력하세요.")
        st.caption("QR은 주소만 공유합니다. 기록은 다른 기기와 자동 동기화되지 않습니다.")
        st.subheader("기록 백업 · 복원")
        st.download_button("JSON 백업 저장",json.dumps(data,ensure_ascii=False,indent=2).encode("utf-8"),f"saving-seed-{today}.json","application/json",type="primary")
        upload=st.file_uploader("이전 버전 포함 JSON 백업",type=["json"])
        agree=st.checkbox("복원하면 현재 기록이 백업으로 교체됩니다")
        if st.button("복원",disabled=upload is None or not agree):
            try:
                if upload.size>2*1024*1024: raise ValueError("size")
                restored=validate_backup(json.loads(upload.getvalue().decode("utf-8-sig")))
                # Old lesson completions retain their previously earned credit.
                st.session_state.seed_data=restored
                st.session_state.flash=True; st.rerun()
            except (ValueError,TypeError,KeyError,UnicodeError,OverflowError,RecursionError): st.error("올바른 백업이 아닙니다. 현재 기록은 유지됩니다.")
        st.caption("이전 버전의 완료 퀴즈는 기존 보상을 유지합니다. 예전 체크형 미션 기록은 복원되지만 새 경험치에는 포함되지 않습니다. 백업에 개인 메모가 포함될 수 있으니 안전하게 보관하세요.")
        with st.expander("배포 방법"):
            st.markdown("1. GitHub 저장소 같은 폴더에 `app.py`와 `requirements.txt` 업로드\n2. Streamlit Community Cloud에서 저장소 연결\n3. Main file path를 `app.py`로 지정해 배포\n4. 위에 배포 주소를 입력하고 QR 다운로드")
            st.code("pip install -r requirements.txt\nstreamlit run app.py",language="bash")
            st.caption("GitHub Pages는 이 Python 서버 앱을 실행하지 못합니다. 선택 사항: Secrets에 PUBLIC_APP_URL을 지정하면 주소가 자동 입력됩니다.")
        with st.expander("모든 기록 초기화"):
            reset=st.checkbox("목표·거래·퀴즈 기록을 모두 삭제합니다")
            if st.button("초기화",disabled=not reset): st.session_state.clear(); st.rerun()


if __name__ == "__main__":
    main()
