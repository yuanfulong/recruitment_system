"""
Agent测试示例 - 演示如何使用招聘Agent

运行方式：
python agent_demo.py
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入Agent
from agent_main import create_recruitment_agent


def demo_1_basic_queries():
    """示例1：基本查询任务"""
    print("\n" + "=" * 70)
    print("📋 示例1：基本查询任务")
    print("=" * 70)

    agent = create_recruitment_agent()

    print("\n场景：HR想了解当前的招聘状况\n")

    # 查询1：列出所有岗位
    print("💬 用户: 列出所有岗位")
    response = agent.chat("列出所有岗位", thread_id="demo1")
    print(f"🤖 Agent:\n{response}\n")

    # 查询2：查看特定岗位
    print("💬 用户: Python岗位的详细统计信息")
    response = agent.chat("Python岗位的详细统计信息", thread_id="demo1")
    print(f"🤖 Agent:\n{response}\n")

    agent.close()


def demo_2_contextual_conversation():
    """示例2：多轮对话（带上下文）"""
    print("\n" + "=" * 70)
    print("💬 示例2：多轮对话（Agent会记住上下文）")
    print("=" * 70)

    agent = create_recruitment_agent()
    thread_id = "demo2_context"

    print("\n场景：HR通过多轮对话深入了解某个岗位\n")

    # 第1轮
    print("💬 用户: 我们有哪些岗位？")
    response = agent.chat("我们有哪些岗位？", thread_id)
    print(f"🤖 Agent:\n{response}\n")

    # 第2轮（利用上下文）
    print("💬 用户: Python岗位有多少候选人？")
    response = agent.chat("Python岗位有多少候选人？", thread_id)
    print(f"🤖 Agent:\n{response}\n")

    # 第3轮（继续利用上下文）
    print("💬 用户: 给我看看分数最高的3个")
    response = agent.chat("给我看看分数最高的3个", thread_id)
    print(f"🤖 Agent:\n{response}\n")

    agent.close()


def demo_3_complex_task():
    """示例3：复杂任务（多工具协作）"""
    print("\n" + "=" * 70)
    print("🎯 示例3：复杂任务 - Agent自主规划和执行")
    print("=" * 70)

    agent = create_recruitment_agent()

    print("\n场景：HR需要找到最适合Python岗位的候选人并获取联系方式\n")

    print("💬 用户: 帮我找Python岗位分数最高的候选人，给我他的详细信息和联系方式")
    response = agent.chat(
        "帮我找Python岗位分数最高的候选人，给我他的详细信息和联系方式",
        thread_id="demo3"
    )
    print(f"🤖 Agent:\n{response}\n")

    print("📊 Agent执行了什么？")
    print("  1. 🔍 搜索Python岗位")
    print("  2. 📋 获取该岗位所有候选人")
    print("  3. 🏆 找出分数最高的候选人")
    print("  4. 📄 获取该候选人的详细信息")
    print("  5. 📧 提取联系方式并格式化输出")

    agent.close()


def demo_4_decision_making():
    """示例4：决策建议"""
    print("\n" + "=" * 70)
    print("🤔 示例4：Agent提供决策建议")
    print("=" * 70)

    agent = create_recruitment_agent()

    print("\n场景：HR需要决策建议\n")

    print("💬 用户: Python岗位的候选人质量怎么样？给我一些招聘建议")
    response = agent.chat(
        "Python岗位的候选人质量怎么样？给我一些招聘建议",
        thread_id="demo4"
    )
    print(f"🤖 Agent:\n{response}\n")

    agent.close()


def demo_5_error_handling():
    """示例5：错误处理和澄清"""
    print("\n" + "=" * 70)
    print("⚠️ 示例5：Agent如何处理模糊或错误的请求")
    print("=" * 70)

    agent = create_recruitment_agent()

    print("\n场景：用户提供了模糊的信息\n")

    # 模糊请求
    print("💬 用户: 那个分数很高的候选人")
    response = agent.chat("那个分数很高的候选人", thread_id="demo5")
    print(f"🤖 Agent:\n{response}\n")

    # 不存在的资源
    print("💬 用户: 候选人999的信息")
    response = agent.chat("候选人999的信息", thread_id="demo5")
    print(f"🤖 Agent:\n{response}\n")

    agent.close()


def demo_6_create_position():
    """示例6：创建岗位（完整流程）"""
    print("\n" + "=" * 70)
    print("🏢 示例6：创建新岗位并自动匹配")
    print("=" * 70)

    agent = create_recruitment_agent()

    print("\n场景：HR需要创建一个新岗位\n")

    print("💬 用户: 帮我创建一个Go语言工程师岗位，要求3年以上经验，熟悉微服务和K8s")
    response = agent.chat(
        "帮我创建一个Go语言工程师岗位，要求3年以上经验，熟悉微服务和K8s",
        thread_id="demo6"
    )
    print(f"🤖 Agent:\n{response}\n")

    print("📊 Agent做了什么？")
    print("  1. 📝 分析岗位描述，提炼核心要求")
    print("  2. 💾 创建岗位记录")
    print("  3. 🔄 自动重新评估所有候选人")
    print("  4. 📈 生成匹配报告")

    agent.close()


def demo_7_candidate_evaluation():
    """示例7：重新评估候选人"""
    print("\n" + "=" * 70)
    print("🔄 示例7：重新评估特定候选人")
    print("=" * 70)

    agent = create_recruitment_agent()

    print("\n场景：HR想重新评估某个候选人对特定岗位的匹配度\n")

    print("💬 用户: 重新评估候选人1对Python岗位的匹配度")
    response = agent.chat(
        "重新评估候选人1对Python岗位的匹配度",
        thread_id="demo7"
    )
    print(f"🤖 Agent:\n{response}\n")

    agent.close()


def demo_8_batch_operations():
    """示例8：批量操作"""
    print("\n" + "=" * 70)
    print("📦 示例8：批量查询和分析")
    print("=" * 70)

    agent = create_recruitment_agent()

    print("\n场景：HR需要批量分析多个岗位\n")

    print("💬 用户: 给我每个岗位的候选人数量和平均分数")
    response = agent.chat(
        "给我每个岗位的候选人数量和平均分数",
        thread_id="demo8"
    )
    print(f"🤖 Agent:\n{response}\n")

    agent.close()


def demo_9_comparison():
    """示例9：Agent vs 传统API对比"""
    print("\n" + "=" * 70)
    print("⚖️ 示例9：Agent模式 vs 传统API模式对比")
    print("=" * 70)

    print("\n任务：找出Python岗位评分最高的候选人\n")

    print("传统API模式（需要多次调用）：")
    print("┌─────────────────────────────────────────────────────────┐")
    print("│ 1. GET /api/positions → 获取所有岗位                     │")
    print("│ 2. 找到Python岗位的ID                                     │")
    print("│ 3. GET /api/positions/1/candidates → 获取候选人          │")
    print("│ 4. 手动排序找出最高分                                     │")
    print("│ 5. GET /api/candidates/5 → 获取详细信息                  │")
    print("│ 6. 人工提取联系方式                                       │")
    print("└─────────────────────────────────────────────────────────┘")
    print("❌ 需要6步操作，需要理解API结构，需要手动处理数据\n")

    print("Agent模式（一句话搞定）：")
    print("┌─────────────────────────────────────────────────────────┐")
    print("│ 用户: 帮我找Python岗位最好的候选人，给我他的联系方式     │")
    print("│                                                          │")
    print("│ Agent: [自动完成所有步骤并返回结果]                      │")
    print("└─────────────────────────────────────────────────────────┘")
    print("✅ 一句话完成，自然语言交互，Agent自主决策\n")

    # 实际运行
    agent = create_recruitment_agent()
    print("实际演示：\n")
    print("💬 用户: 帮我找Python岗位最好的候选人，给我他的联系方式")
    response = agent.chat(
        "帮我找Python岗位最好的候选人，给我他的联系方式",
        thread_id="demo9"
    )
    print(f"🤖 Agent:\n{response}\n")

    agent.close()


def demo_10_tool_inspection():
    """示例10：查看可用工具"""
    print("\n" + "=" * 70)
    print("🔧 示例10：查看Agent的所有能力（工具）")
    print("=" * 70)

    agent = create_recruitment_agent()

    tools = agent.list_available_tools()

    print(f"\n🤖 Agent共有 {len(tools)} 个工具：\n")

    for i, tool in enumerate(tools, 1):
        print(f"{i}. 🔧 {tool['name']}")
        print(f"   📝 {tool['description']}\n")

    agent.close()


def interactive_demo():
    """交互式演示"""
    print("\n" + "=" * 70)
    print("🎮 交互式演示 - 你来试试！")
    print("=" * 70)

    agent = create_recruitment_agent()

    print("""
请输入你的问题，Agent会自动理解并执行。

示例问题：
- "列出所有岗位"
- "Python岗位有多少候选人？"
- "帮我找分数最高的3个候选人"
- "创建一个前端工程师岗位"

输入 'quit' 退出
""")

    thread_id = "interactive_demo"

    while True:
        try:
            user_input = input("\n💬 你: ").strip()

            if not user_input:
                continue

            if user_input.lower() == 'quit':
                print("\n再见！👋")
                break

            print("\n🤖 Agent: ", end="", flush=True)
            response = agent.chat(user_input, thread_id)
            print(response)

        except KeyboardInterrupt:
            print("\n\n再见！👋")
            break
        except Exception as e:
            print(f"\n错误: {str(e)}")

    agent.close()


def main():
    """主函数 - 运行所有演示"""

    print("""
╔═══════════════════════════════════════════════════════════════╗
║          🤖 招聘Agent系统 - 功能演示                          ║
╚═══════════════════════════════════════════════════════════════╝

这个演示将展示Agent如何通过工具调用来完成各种招聘任务。

注意：确保你的环境变量已正确配置：
- DATABASE_URL
- ANTHROPIC_API_KEY
""")

    print("\n选择要运行的演示：")
    print("1. 基本查询任务")
    print("2. 多轮对话（上下文）")
    print("3. 复杂任务（多工具协作）")
    print("4. 决策建议")
    print("5. 错误处理")
    print("6. 创建岗位")
    print("7. 重新评估候选人")
    print("8. 批量操作")
    print("9. Agent vs API对比")
    print("10. 查看所有工具")
    print("11. 交互式演示")
    print("0. 运行所有演示")

    choice = input("\n请选择 (0-11): ").strip()

    demos = {
        '1': demo_1_basic_queries,
        '2': demo_2_contextual_conversation,
        '3': demo_3_complex_task,
        '4': demo_4_decision_making,
        '5': demo_5_error_handling,
        '6': demo_6_create_position,
        '7': demo_7_candidate_evaluation,
        '8': demo_8_batch_operations,
        '9': demo_9_comparison,
        '10': demo_10_tool_inspection,
        '11': interactive_demo,
    }

    if choice == '0':
        # 运行所有演示
        for demo_func in demos.values():
            if demo_func != interactive_demo:  # 跳过交互式
                try:
                    demo_func()
                    input("\n按Enter继续下一个演示...")
                except Exception as e:
                    print(f"\n错误: {str(e)}")
    elif choice in demos:
        demos[choice]()
    else:
        print("无效选择")

    print("\n" + "=" * 70)
    print("演示结束！要查看更多使用方法，请阅读 AGENT_GUIDE.md")
    print("=" * 70)


if __name__ == "__main__":
    main()