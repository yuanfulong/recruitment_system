"""
数据库诊断脚本 - 检查候选人数据是否正确存储
"""
import os
from dotenv import load_dotenv

load_dotenv()

from models import init_db, get_session, Candidate, Position, CandidatePositionMatch
from sqlalchemy import func

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///recruitment.db")


def diagnose_database():
    """诊断数据库中的数据"""

    print("=" * 70)
    print("📊 数据库诊断报告")
    print("=" * 70)

    try:
        # 初始化数据库连接
        engine = init_db(DATABASE_URL)
        session = get_session(engine)

        print(f"\n✓ 数据库连接成功: {DATABASE_URL}\n")

        # 1. 检查候选人表
        print("1️⃣  候选人表 (Candidate)")
        print("-" * 70)

        candidates = session.query(Candidate).all()
        print(f"总候选人数: {len(candidates)}\n")

        if candidates:
            for i, candidate in enumerate(candidates, 1):
                print(f"候选人 {i}:")
                print(f"  - ID: {candidate.candidate_id}")
                print(f"  - 姓名: {candidate.name}")
                print(f"  - 年龄: {candidate.age}")
                print(f"  - 邮箱: {candidate.email}")
                print(f"  - 电话: {candidate.phone}")
                print(f"  - 有明确意向: {candidate.has_explicit_position}")
                print(f"  - 意向岗位: {candidate.explicit_position}")
                print(f"  - 当前分配岗位: {candidate.auto_matched_position}")
                print(f"  - 当前分配分数: {candidate.auto_matched_position_score}")
                print(f"  - 岗位是否锁定: {candidate.is_position_locked}")
                print(f"  - 上传时间: {candidate.uploaded_at}")
                print()
        else:
            print("⚠️  候选人表为空！")

        # 2. 检查岗位表
        print("\n2️⃣  岗位表 (Position)")
        print("-" * 70)

        positions = session.query(Position).all()
        print(f"总岗位数: {len(positions)}\n")

        if positions:
            for i, position in enumerate(positions, 1):
                print(f"岗位 {i}:")
                print(f"  - ID: {position.position_id}")
                print(f"  - 名称: {position.name}")
                print(f"  - 是否活跃: {position.is_active}")
                print(f"  - 候选人总数: {position.total_candidates}")
                print(f"  - 合格人数: {position.qualified_count}")
                print(
                    f"  - A级: {position.a_grade_count}, B级: {position.b_grade_count}, C级: {position.c_grade_count}, D级: {position.d_grade_count}")
                print(f"  - 创建时间: {position.created_at}")
                print()
        else:
            print("⚠️  岗位表为空！")

        # 3. 检查匹配表
        print("\n3️⃣  匹配记录表 (CandidatePositionMatch)")
        print("-" * 70)

        matches = session.query(CandidatePositionMatch).all()
        print(f"总匹配记录数: {len(matches)}\n")

        if matches:
            for i, match in enumerate(matches, 1):
                candidate = session.query(Candidate).filter(
                    Candidate.candidate_id == match.candidate_id
                ).first()
                position = session.query(Position).filter(
                    Position.position_id == match.position_id
                ).first()

                print(f"匹配记录 {i}:")
                print(f"  - 匹配ID: {match.match_id}")
                print(f"  - 候选人: {candidate.name if candidate else 'N/A'} (ID: {match.candidate_id})")
                print(f"  - 岗位: {position.name if position else 'N/A'} (ID: {match.position_id})")
                print(f"  - 评分: {match.overall_score}/100")
                print(f"  - 等级: {match.grade}")
                print(f"  - 是否合格: {match.is_qualified}")
                print(f"  - 评估时间: {match.evaluated_at}")
                print()
        else:
            print("⚠️  匹配记录表为空！")

        # 4. 数据一致性检查
        print("\n4️⃣  数据一致性检查")
        print("-" * 70)

        issues = []

        # 检查：候选人是否都有匹配记录
        for candidate in candidates:
            candidate_matches = session.query(CandidatePositionMatch).filter(
                CandidatePositionMatch.candidate_id == candidate.candidate_id
            ).count()

            if candidate_matches == 0:
                issues.append(f"⚠️  候选人 {candidate.name} (ID: {candidate.candidate_id}) 没有任何匹配记录")

        # 检查：岗位统计数是否正确
        for position in positions:
            actual_count = session.query(CandidatePositionMatch).filter(
                CandidatePositionMatch.position_id == position.position_id
            ).count()

            if actual_count != position.total_candidates:
                issues.append(f"⚠️  岗位 {position.name} (ID: {position.position_id}) 统计数不正确：")
                issues.append(f"     数据库记录: {position.total_candidates}, 实际匹配数: {actual_count}")

        if issues:
            print("\n发现以下问题：")
            for issue in issues:
                print(issue)
        else:
            print("✓ 所有数据一致性检查通过")

        # 5. 诊断结论
        print("\n" + "=" * 70)
        print("📋 诊断结论")
        print("=" * 70)

        if len(candidates) == 0:
            print("❌ 问题：候选人表为空")
            print("   可能原因：")
            print("   1. 简历还未上传")
            print("   2. 上传过程中出错，数据未保存")
            print("   3. 使用了错误的数据库文件")
            print("\n   解决方案：")
            print("   - 重新上传简历：curl -X POST '/api/candidates/upload' -F 'file=@resume.pdf'")
            print("   - 或检查数据库文件路径是否正确")

        elif len(positions) == 0:
            print("❌ 问题：岗位表为空")
            print("   可能原因：岗位还未创建")
            print("\n   解决方案：")
            print("   - 先创建岗位：curl -X POST '/api/positions' -d '{...}'")

        elif len(matches) == 0:
            print("❌ 问题：有候选人和岗位，但没有匹配记录")
            print("   可能原因：")
            print("   1. 候选人是在岗位创建之前上传的（旧版本系统）")
            print("   2. 匹配记录创建失败")
            print("\n   解决方案：")
            print("   - 重新上传候选人简历，会自动生成匹配记录")

        elif issues:
            print("⚠️  数据存在，但有一致性问题")
            print("   建议：检查上述发现的具体问题")

        else:
            print("✅ 数据库状态正常！")
            print(f"   - {len(candidates)} 个候选人")
            print(f"   - {len(positions)} 个岗位")
            print(f"   - {len(matches)} 条匹配记录")

        session.close()

    except Exception as e:
        print(f"\n❌ 诊断过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    diagnose_database()