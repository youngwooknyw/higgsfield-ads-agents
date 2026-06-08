# -*- coding: utf-8 -*-
"""
crema_review_insights.py
------------------------
크레마(Crema) 공식 Open API 기반 상품 리뷰 조회 + 광고 소구포인트 도출 (단일 파일, 표준 라이브러리만 사용).

[이전(移轉)에 필요한 파일은 단 2개]
  1) 이 스크립트 (crema_review_insights.py)
  2) .crema_credentials.json   (app_id / secret_key 등 — 절대 git/공유 금지)

[사용법]
  # 풀코드(컬러 포함) 직접 지정 — 가장 확실
  python crema_review_insights.py DXRS75063-BKS DXRS75063-WHS

  # PART_CD만 주면 기본 컬러 후보를 자동 탐색(있는 컬러만 수집)
  python crema_review_insights.py DXRS75063
  python crema_review_insights.py DXRS75063 --colors BKS,WHS,IND,IVD

[산출물]
  crema_out/{PART_CD}_reviews.json   원본 리뷰 전체(JSON)
  crema_out/{PART_CD}_insights.txt   컨셉별 언급수 + 소구포인트 후보 리포트

주의: 조회는 반드시 '컬러 코드 포함' 풀코드여야 함(예: DXRS75063-BKS). PART_CD만으로는 404.
"""

import sys
import os
import re
import json
import time
import argparse
import urllib.request
import urllib.parse
import urllib.error
from collections import OrderedDict

# Windows 콘솔(cp949)에서 한글 깨짐 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
CRED_PATH = os.path.join(HERE, ".crema_credentials.json")
TOKEN_CACHE = os.path.join(HERE, ".crema_token.json")
OUT_DIR = os.path.join(HERE, "crema_out")

# PART_CD만 입력했을 때 자동 탐색할 기본 컬러 후보(있는 것만 수집, 없으면 404로 조용히 skip)
DEFAULT_COLORS = [
    "BKS", "WHS", "IVD", "IND", "NVS", "GYS", "BES", "KAD", "MGS", "DWS",
    "PCS", "BLS", "GNS", "RES", "PKS", "YLS", "BRS", "ORS", "DGS", "LGS",
]

# 소구포인트 컨셉 사전: 컨셉명 -> 키워드 목록(부분일치)
CONCEPTS = OrderedDict([
    ("시원함/여름",   ["시원", "쿨", "냉감", "여름", "통풍", "땀", "더위", "서늘", "청량", "얇아", "얇고"]),
    ("소재/품질",     ["소재", "원단", "재질", "품질", "퀄리티", "퀄러티", "마감", "도톰", "보들", "부드럽", "촉감", "쫀쫀", "탄탄"]),
    ("핏/사이즈",     ["핏", "사이즈", "사이징", "오버핏", "슬림", "넉넉", "여유", "정사이즈", "기장", "크게", "작게", "품이"]),
    ("착용감/편안함", ["편안", "편하", "편함", "착용감", "가볍", "입기 편", "입기편", "부담없"]),
    ("디자인/색상",   ["디자인", "색상", "컬러", "색감", "예쁘", "이쁘", "깔끔", "심플", "무난", "세련", "포인트", "와펜", "로고"]),
    ("가성비",        ["가성비", "가격", "저렴", "합리", "세일", "할인", "값", "착한 가격"]),
    ("활동성",        ["활동", "운동", "야외", "등산", "트레킹", "액티", "골프", "캠핑"]),
    ("재구매/추천",   ["재구매", "또 구매", "또 살", "추천", "잘 샀", "잘샀", "재주문", "또 주문"]),
    ("배송/CS",       ["배송", "빠르", "도착", "포장", "교환", "환불", "문의", "친절", "응대"]),
])

# 광고 '제품 소구점'으로 직접 쓰기 적합한 컨셉(서비스/감성 제외)
AD_RELEVANT = ["시원함/여름", "소재/품질", "핏/사이즈", "착용감/편안함", "디자인/색상", "가성비", "활동성"]


def load_credentials():
    if not os.path.exists(CRED_PATH):
        sys.exit("[오류] .crema_credentials.json 을 찾을 수 없습니다. 스크립트와 같은 폴더에 두세요.")
    with open(CRED_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_token(cred, force=False):
    """토큰 캐시 재사용(TTL 60일). 만료 임박/없음/force 시 재발급."""
    if not force and os.path.exists(TOKEN_CACHE):
        try:
            with open(TOKEN_CACHE, encoding="utf-8") as f:
                t = json.load(f)
            if t.get("_expires_at", 0) - time.time() > 86400:  # 하루 이상 남았으면 재사용
                return t["access_token"]
        except Exception:
            pass

    host = cred["api_host_live"]
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": cred["app_id"],
        "client_secret": cred["secret_key"],
    }).encode()
    req = urllib.request.Request(host + "/oauth/token", data=body, method="POST")
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=20))
    except urllib.error.HTTPError as e:
        sys.exit("[오류] 토큰 발급 실패 (HTTP %s): %s" % (e.code, e.read()[:200]))
    resp["_expires_at"] = time.time() + int(resp.get("expires_in", 5184000))
    with open(TOKEN_CACHE, "w", encoding="utf-8") as f:
        json.dump(resp, f)
    return resp["access_token"]


def fetch_reviews(host, token, product_code, max_pages=200):
    """단일 풀코드의 전체 리뷰를 page 페이지네이션으로 수집. (200 OK가 빈 배열이면 종료)
    반환: (reviews list, status) — status: 'ok' | 'notfound' | 'error:<code>'"""
    out = []
    page = 1
    while page <= max_pages:
        url = host + "/v1/reviews?" + urllib.parse.urlencode({
            "product_code": product_code, "page": page,
        })
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
        try:
            data = json.load(urllib.request.urlopen(req, timeout=20))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return out, ("ok" if out else "notfound")
            return out, "error:%s" % e.code
        if not data:
            break
        out.extend(data)
        if len(data) < 30:  # 한 페이지 기본 30건 미만이면 마지막 페이지
            break
        page += 1
    return out, "ok"


def dedupe(reviews):
    """동일 사용자가 컬러별 SKU에 똑같이 남긴 중복을 (이름,본문) 기준으로 제거."""
    seen = set()
    uniq = []
    for r in reviews:
        key = (r.get("user_name", ""), (r.get("message") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq


def analyze(reviews):
    """컨셉별 '언급한 리뷰 수' 집계 + 매칭 키워드 샘플."""
    counts = OrderedDict((c, 0) for c in CONCEPTS)
    samples = OrderedDict((c, []) for c in CONCEPTS)
    for r in reviews:
        msg = (r.get("message") or "")
        for concept, kws in CONCEPTS.items():
            hit = next((k for k in kws if k in msg), None)
            if hit:
                counts[concept] += 1
                if len(samples[concept]) < 3:
                    snippet = re.sub(r"\s+", " ", msg).strip()[:40]
                    samples[concept].append(snippet)
    return counts, samples


def build_report(part_cd, codes_found, codes_missing, reviews_raw, reviews, counts, samples):
    lines = []
    scores = [r["score"] for r in reviews if isinstance(r.get("score"), (int, float))]
    avg = round(sum(scores) / len(scores), 2) if scores else 0
    lines.append("=" * 60)
    lines.append("상품번호: %s" % part_cd)
    lines.append("수집 컬러: %s" % (", ".join(codes_found) if codes_found else "(없음)"))
    if codes_missing:
        lines.append("미존재/리뷰없음 컬러(skip): %s" % ", ".join(codes_missing))
    lines.append("총 리뷰: 원본 %d건 / 중복제거 %d건" % (len(reviews_raw), len(reviews)))
    lines.append("평균 별점: %s" % avg)
    lines.append("")
    lines.append("=== 컨셉별 언급 리뷰 수 (중복제거 기준) ===")
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    for concept, n in ranked:
        bar = "■" * min(n, 30)
        tag = "" if concept in AD_RELEVANT else "  (서비스/감성-소구점 제외)"
        lines.append("%3d  %-12s %s%s" % (n, concept, bar, tag))
    lines.append("")
    lines.append("=== 광고 소구포인트 후보 (제품 소구점만, 빈도순) ===")
    ad_ranked = [(c, counts[c]) for c, _ in ranked if c in AD_RELEVANT and counts[c] > 0]
    for i, (concept, n) in enumerate(ad_ranked, start=1):
        ex = " / ".join(samples[concept]) if samples[concept] else ""
        lines.append("소구점 %d순위: %s  (%d건)" % (i, concept, n))
        if ex:
            lines.append("    근거 예시: %s" % ex)
    lines.append("")
    lines.append("[참고] 최종 소구점은 WORKFLOW.md 2절 룰에 따라")
    lines.append("       위 빈도 1위 ∩ 스타일가이드 FABRIC/FIT 강조점과 교차 확정하세요.")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="크레마 리뷰 조회 + 광고 소구포인트 도출")
    ap.add_argument("codes", nargs="+", help="풀코드(DXRS75063-BKS) 또는 PART_CD(DXRS75063)")
    ap.add_argument("--colors", help="PART_CD만 줬을 때 탐색할 컬러(쉼표구분). 예: BKS,WHS,IND")
    ap.add_argument("--no-dedupe", action="store_true", help="중복(동일 본문) 제거 비활성화")
    args = ap.parse_args()

    cred = load_credentials()
    host = cred["api_host_live"]
    token = get_token(cred)

    # 입력 정규화: 풀코드(하이픈 有)는 그대로, PART_CD는 컬러 후보를 붙여 탐색
    full_codes = [c for c in args.codes if "-" in c]
    part_cds = [c for c in args.codes if "-" not in c]
    colors = [c.strip().upper() for c in args.colors.split(",")] if args.colors else DEFAULT_COLORS

    os.makedirs(OUT_DIR, exist_ok=True)

    # PART_CD 단위로 그룹핑 (풀코드는 자기 PART_CD로 묶음)
    groups = OrderedDict()
    for fc in full_codes:
        part = fc.split("-")[0]
        groups.setdefault(part, set()).add(fc)
    for pc in part_cds:
        groups.setdefault(pc, set())
        for col in colors:
            groups[pc].add("%s-%s" % (pc, col))

    for part_cd, candidate_codes in groups.items():
        reviews_raw, found, missing = [], [], []
        for code in sorted(candidate_codes):
            revs, status = fetch_reviews(host, token, code)
            if status == "ok" and revs:
                reviews_raw.extend(revs)
                found.append(code.split("-", 1)[1] if "-" in code else code)
                print("  [OK]   %-16s %3d건" % (code, len(revs)))
            elif status == "notfound":
                missing.append(code.split("-", 1)[1] if "-" in code else code)
            else:
                print("  [WARN] %-16s %s" % (code, status))
                missing.append(code.split("-", 1)[1] if "-" in code else code)

        if not reviews_raw:
            print("[%s] 수집된 리뷰가 없습니다. 컬러 코드를 --colors 로 지정해 보세요." % part_cd)
            continue

        reviews = reviews_raw if args.no_dedupe else dedupe(reviews_raw)
        counts, samples = analyze(reviews)
        report = build_report(part_cd, found, missing, reviews_raw, reviews, counts, samples)

        rev_path = os.path.join(OUT_DIR, "%s_reviews.json" % part_cd)
        rep_path = os.path.join(OUT_DIR, "%s_insights.txt" % part_cd)
        with open(rev_path, "w", encoding="utf-8") as f:
            json.dump(reviews_raw, f, ensure_ascii=False, indent=2)
        with open(rep_path, "w", encoding="utf-8") as f:
            f.write(report)

        print("\n" + report)
        print("\n저장: %s\n      %s" % (rev_path, rep_path))


if __name__ == "__main__":
    main()
