"""Neo4j 데이터와 인덱스 확인"""
import asyncio
from app.core.neo4j import get_neo4j_driver

async def main():
    driver = get_neo4j_driver()
    
    print("="*80)
    print("1. 인덱스 확인")
    print("="*80)
    async with driver.session() as session:
        try:
            result = await session.run("SHOW INDEXES")
            records = await result.data()
            for r in records:
                print(f"  {r.get('name', 'N/A')}: {r.get('type', 'N/A')}")
            
            if not any(r.get('name') == 'decision_search' for r in records):
                print("  ⚠️ decision_search 인덱스가 없습니다!")
        except Exception as e:
            print(f"  인덱스 조회 실패: {e}")
    
    print("\n" + "="*80)
    print("2. user-1e6382d1의 결정사항 직접 조회 (FULLTEXT 없이)")
    print("="*80)
    async with driver.session() as session:
        cypher = """
        MATCH (u:User {id: $user_id})-[:PARTICIPATED_IN]->(m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(d:Decision)
        RETURN d.id, d.content, d.status, d.created_at, count(*) as total
        LIMIT 5
        """
        result = await session.run(cypher, user_id="user-1e6382d1")
        records = await result.data()
        print(f"결과: {len(records)}개")
        for r in records:
            print(f"  - {r['d.id']}: {r['d.content'][:60]}...")
    
    print("\n" + "="*80)
    print("3. FULLTEXT 인덱스로 검색 테스트")
    print("="*80)
    async with driver.session() as session:
        cypher = """
        CALL db.index.fulltext.queryNodes('decision_search', '결정')
        YIELD node, score
        RETURN node.id, node.content, score
        LIMIT 5
        """
        try:
            result = await session.run(cypher)
            records = await result.data()
            print(f"'결정' 검색 결과: {len(records)}개")
            for r in records:
                print(f"  - {r['node.id']}: {r['node.content'][:60]}... (점수: {r['score']:.2f})")
        except Exception as e:
            print(f"⚠️ FULLTEXT 검색 실패: {e}")
    
    print("\n" + "="*80)
    print("4. user-1e6382d1의 결정사항을 FULLTEXT로 검색")
    print("="*80)
    async with driver.session() as session:
        cypher = """
        CALL db.index.fulltext.queryNodes('decision_search', '결정')
        YIELD node, score
        MATCH (a:Agenda)-[:HAS_DECISION]->(node)
        MATCH (m:Meeting)-[:CONTAINS]->(a)
        WHERE (m)<-[:PARTICIPATED_IN]-(:User {id: $user_id})
        RETURN node.id, node.content, score
        LIMIT 5
        """
        try:
            result = await session.run(cypher, user_id="user-1e6382d1")
            records = await result.data()
            print(f"결과: {len(records)}개")
            for r in records:
                print(f"  - {r['node.id']}: {r['node.content'][:60]}... (점수: {r['score']:.2f})")
        except Exception as e:
            print(f"⚠️ 검색 실패: {e}")
    
    await driver.close()

if __name__ == "__main__":
    asyncio.run(main())
