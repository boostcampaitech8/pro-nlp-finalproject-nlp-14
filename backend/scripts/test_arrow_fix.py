#!/usr/bin/env python3
"""유니코드 화살표 수정 테스트 스크립트"""

import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.infrastructure.graph.workflows.mit_search.nodes.cypher_generation import (
    _sanitize_generated_cypher,
    _is_safe_cypher,
    _evaluate_cypher_quality,
)

def test_sanitization():
    """테스트 1: Sanitization 함수 - 유니코드 화살표 변환"""
    print("\n" + "="*80)
    print("테스트 1: Sanitization 함수")
    print("="*80)

    test_cases = [
        # 우측 화살표
        ("MATCH (u:User)→[:PARTICIPATED_IN]→(m:Meeting)", "MATCH (u:User)->[:PARTICIPATED_IN]->(m:Meeting)"),
        ("MATCH (u:User)⇒[:PARTICIPATED_IN]⇒(m:Meeting)", "MATCH (u:User)->[:PARTICIPATED_IN]->(m:Meeting)"),
        ("MATCH (u:User)➡[:PARTICIPATED_IN]➡(m:Meeting)", "MATCH (u:User)->[:PARTICIPATED_IN]->(m:Meeting)"),
        # 좌측 화살표
        ("MATCH (u:User)←[:MEMBER_OF]←(t:Team)", "MATCH (u:User)<-[:MEMBER_OF]<-(t:Team)"),
        ("MATCH (u:User)⇐[:MEMBER_OF]⇐(t:Team)", "MATCH (u:User)<-[:MEMBER_OF]<-(t:Team)"),
        ("MATCH (u:User)⬅[:MEMBER_OF]⬅(t:Team)", "MATCH (u:User)<-[:MEMBER_OF]<-(t:Team)"),
        # Em dash
        ("MATCH (u:User)—[:REL]—(m:Node)", "MATCH (u:User)-[:REL]-(m:Node)"),
        # 혼합
        ("MATCH (u:User)→[:A]→(m:M)←[:B]←(d:D)", "MATCH (u:User)->[:A]->(m:M)<-[:B]<-(d:D)"),
    ]

    passed = 0
    failed = 0

    for input_query, expected_output in test_cases:
        result = _sanitize_generated_cypher(input_query)

        # 유니코드 화살표가 없는지 확인
        unicode_arrows = ['→', '←', '⇒', '⇐', '➡', '⬅']
        has_unicode = any(arrow in result for arrow in unicode_arrows)

        # Em dash는 별도로 확인 (방향성 없는 관계에서 사용될 수 있음)
        has_em_dash = '—' in result

        # ASCII 화살표 또는 하이픈이 있는지 확인
        has_correct_arrow = '->' in result or '<-' in result or ('-' in result and not has_em_dash)

        if not has_unicode and not has_em_dash and has_correct_arrow:
            print(f"✓ PASS: {input_query[:50]}...")
            passed += 1
        else:
            print(f"✗ FAIL: {input_query[:50]}...")
            print(f"  Expected: {expected_output}")
            print(f"  Got:      {result}")
            print(f"  Unicode arrows: {has_unicode}")
            print(f"  Em dash: {has_em_dash}")
            print(f"  Correct arrow: {has_correct_arrow}")
            failed += 1

    print(f"\n결과: {passed} passed, {failed} failed")
    return failed == 0


def test_validation():
    """테스트 2: Validation 함수 - 유니코드 화살표 검출"""
    print("\n" + "="*80)
    print("테스트 2: Validation 함수")
    print("="*80)

    # 유니코드 화살표가 있는 쿼리 (should FAIL validation)
    bad_queries = [
        "MATCH (u:User)→[:PARTICIPATED_IN]→(m:Meeting) RETURN m.id AS id, 1.0 AS score, 'test' AS graph_context LIMIT 20",
        "MATCH (u:User)←[:MEMBER_OF]←(t:Team) RETURN t.id AS id, 1.0 AS score, 'test' AS graph_context LIMIT 20",
    ]

    # ASCII 화살표가 있는 쿼리 (should PASS validation)
    good_queries = [
        "MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting) RETURN m.id AS id, 1.0 AS score, 'test' AS graph_context LIMIT 20",
        "MATCH (u:User)<-[:MEMBER_OF]-(t:Team) RETURN t.id AS id, 1.0 AS score, 'test' AS graph_context LIMIT 20",
    ]

    passed = 0
    failed = 0

    print("\n유니코드 화살표 쿼리 (validation 실패 예상):")
    for query in bad_queries:
        is_safe = _is_safe_cypher(query)
        if not is_safe:
            print(f"✓ PASS: 유니코드 화살표 검출됨")
            passed += 1
        else:
            print(f"✗ FAIL: 유니코드 화살표 미검출")
            print(f"  Query: {query[:50]}...")
            failed += 1

    print("\nASCII 화살표 쿼리 (validation 통과 예상):")
    for query in good_queries:
        is_safe = _is_safe_cypher(query)
        if is_safe:
            print(f"✓ PASS: 정상 쿼리 통과")
            passed += 1
        else:
            print(f"✗ FAIL: 정상 쿼리 거부")
            print(f"  Query: {query[:50]}...")
            failed += 1

    print(f"\n결과: {passed} passed, {failed} failed")
    return failed == 0


def test_quality_evaluation():
    """테스트 3: Quality Evaluation - 유니코드 화살표 이슈 검출"""
    print("\n" + "="*80)
    print("테스트 3: Quality Evaluation 함수")
    print("="*80)

    # 유니코드 화살표가 있는 쿼리
    query_with_unicode = "MATCH (u:User)→[:PARTICIPATED_IN]→(m:Meeting) RETURN m.id AS id, 1.0 AS score, 'test' AS graph_context LIMIT 20"

    # ASCII 화살표가 있는 쿼리
    query_with_ascii = "MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting) RETURN m.id AS id, 1.0 AS score, 'test' AS graph_context LIMIT 20"

    passed = 0
    failed = 0

    issues_unicode = _evaluate_cypher_quality(query_with_unicode)
    if "unicode_arrows_detected" in issues_unicode:
        print(f"✓ PASS: 유니코드 화살표 이슈 검출됨")
        passed += 1
    else:
        print(f"✗ FAIL: 유니코드 화살표 이슈 미검출")
        print(f"  Issues: {issues_unicode}")
        failed += 1

    issues_ascii = _evaluate_cypher_quality(query_with_ascii)
    if "unicode_arrows_detected" not in issues_ascii:
        print(f"✓ PASS: ASCII 화살표 쿼리에서 이슈 없음")
        passed += 1
    else:
        print(f"✗ FAIL: ASCII 화살표 쿼리에서 잘못된 이슈 검출")
        print(f"  Issues: {issues_ascii}")
        failed += 1

    print(f"\n결과: {passed} passed, {failed} failed")
    return failed == 0


def test_original_problem_query():
    """테스트 4: 원본 문제 쿼리 테스트"""
    print("\n" + "="*80)
    print("테스트 4: 원본 문제 쿼리")
    print("="*80)

    original_query = """MATCH (u:User {id: '80c43e89-f1ac-42ba-99a6-c4a74f126d4e'})-[r:PARTICIPATED_IN]→(m:Meeting)
RETURN m.id AS id, m.title AS title, m.created_at AS created_at, 1.0 AS score,
       '최하영 님이 참여한 회의: ' + m.title AS graph_context
ORDER BY m.created_at DESC
LIMIT 20"""

    print(f"\n원본 쿼리 (유니코드 화살표 포함):")
    print(original_query[:100] + "...")

    # Sanitization 적용
    sanitized = _sanitize_generated_cypher(original_query)

    print(f"\nSanitization 후:")
    print(sanitized[:100] + "...")

    # 검증
    unicode_arrows = ['→', '←', '⇒', '⇐', '➡', '⬅']
    has_unicode = any(arrow in sanitized for arrow in unicode_arrows)
    has_ascii_right = '->' in sanitized

    if not has_unicode and has_ascii_right:
        print(f"\n✓ PASS: 유니코드 화살표가 ASCII로 변환되었습니다")
        print(f"  → 변환 확인: {'->' in sanitized}")
        print(f"  유니코드 없음: {not has_unicode}")
        return True
    else:
        print(f"\n✗ FAIL: 변환 실패")
        print(f"  유니코드 남음: {has_unicode}")
        print(f"  ASCII 화살표: {has_ascii_right}")
        return False


if __name__ == "__main__":
    print("유니코드 화살표 수정 테스트 시작")
    print("="*80)

    results = []

    # 각 테스트 실행
    results.append(("Sanitization", test_sanitization()))
    results.append(("Validation", test_validation()))
    results.append(("Quality Evaluation", test_quality_evaluation()))
    results.append(("Original Problem Query", test_original_problem_query()))

    # 최종 결과
    print("\n" + "="*80)
    print("최종 결과")
    print("="*80)

    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n모든 테스트 통과! 🎉")
        sys.exit(0)
    else:
        print("\n일부 테스트 실패")
        sys.exit(1)
