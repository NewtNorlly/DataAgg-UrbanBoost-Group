"""
多智能体协作决策模拟
"""
import dashscope
import json
import time

dashscope.api_key = "sk-ws-H.EMXIDYH.RRck.MEUCIQDHp0XqUKzYR8qG0aPpbTRjPHKy9bePLZ_4foECaF_mhQIgf3zrYzRfnU5u5t74Cgyiuee4PUdHJgASPdF-BySFpDs"


CASE_TYPE2 = {
    "格网ID": "2237", "片区": "武汉07",
    "更新潜力": 0.677, "内部品质": 0.373, "外部供给": 0.278,
    "街巷空间与交通通达": 0.512, "建筑风貌与界面品质": 0.525,
    "便民生活与服务韧性": 0.325, "环境秩序与生态韧性": 0.521,
    "公共安全与心理感知": 0.438, "场所氛围与情感价值": 0.312,
}

CASE_TYPE3 = {
    "格网ID": "3942", "片区": "武汉11",
    "更新潜力": 0.773, "内部品质": 0.426, "外部供给": 0.047,
    "街巷空间与交通通达": 0.615, "建筑风貌与界面品质": 0.550,
    "便民生活与服务韧性": 0.330, "环境秩序与生态韧性": 0.629,
    "公共安全与心理感知": 0.550, "场所氛围与情感价值": 0.335,
}


GOV_PROMPT = """你是武汉市城市更新主管部门的规划师。
你的职责：推动城市更新，保障公共利益，兼顾财政可持续与社会公平。

当前更新地块诊断结果：
- 片区：{片区}，格网ID：{格网ID}
- 更新潜力指数：{更新潜力}（0-1，越高越紧迫）
- 内部品质指数：{内部品质}
- 外部供给指数：{外部供给}
- 六维感知：街巷交通{街巷空间与交通通达}、建筑风貌{建筑风貌与界面品质}、
  便民生活{便民生活与服务韧性}、环境秩序{环境秩序与生态韧性}、
  公共安全{公共安全与心理感知}、场所氛围{场所氛围与情感价值}

请提出你的初步更新方案（200字以内），说明：更新模式、核心举措、资金来源。"""


ENT_PROMPT = """你是武汉本地房地产开发企业的投资总监。
你的职责：评估更新项目的投资可行性，确保合理回报。

当前地块条件：
- 区位：{片区}
- 更新潜力：{更新潜力}
- 内部品质：{内部品质}
- 外部供给：{外部供给}

政府初步方案如下：
{gov_plan}

请发表你的意见（200字以内），说明：是否愿意参与、要求什么条件、担心什么风险。"""


RES_PROMPT = """你是该地块的社区居民代表。
你的诉求：改善居住环境、合理的补偿安置、保留邻里关系。

当前地块问题：
- 内部品质：{内部品质}（街巷交通{街巷空间与交通通达}，公共安全{公共安全与心理感知}，
  建筑风貌{建筑风貌与界面品质}）
- 外部供给：{外部供给}（菜市场、社区卫生、公交等）

政府初步方案：
{gov_plan}

企业意见：
{ent_opinion}

请表达你的诉求（200字以内），说明：支持什么、反对什么、最关心什么。"""


def call_llm(prompt, role_name):
    response = dashscope.Generation.call(
        model="qwen-plus",
        messages=[{"role": "user", "content": prompt}],
        result_format="message"
    )
    if response.status_code == 200:
        return response.output.choices[0].message.content
    else:
        print(f"{role_name} 调用失败: {response.code} {response.message}")
        return ""


def simulate(case, case_name):
    print("\n" + "=" * 70)
    print(f"多智能体模拟：{case_name}")
    print("=" * 70)

    # 第1轮：政府提方案
    print("\n【第1轮】政府提出初步方案")
    gov_plan = call_llm(GOV_PROMPT.format(**case), "政府")
    print(f"政府：\n{gov_plan}\n")
    time.sleep(2)

    # 第1轮：企业反馈
    print("【第1轮】企业评估")
    ent_opinion = call_llm(ENT_PROMPT.format(gov_plan=gov_plan, **case), "企业")
    print(f"企业：\n{ent_opinion}\n")
    time.sleep(2)

    # 第1轮：居民反馈
    print("【第1轮】居民反馈")
    res_opinion = call_llm(
        RES_PROMPT.format(gov_plan=gov_plan, ent_opinion=ent_opinion, **case),
        "居民"
    )
    print(f"居民：\n{res_opinion}\n")
    time.sleep(2)

    # 第2轮：政府调整
    print("【第2轮】政府综合反馈，调整方案")
    gov_plan_v2 = call_llm(
        f"""你是政府规划师。

第1轮方案：{gov_plan}

企业反馈：{ent_opinion}

居民反馈：{res_opinion}

请综合三方诉求，提出调整后的最终方案（250字以内），说明：
1. 更新模式
2. 核心举措
3. 对企业和居民诉求的回应
4. 资金与实施安排""",
        "政府"
    )
    print(f"政府最终方案：\n{gov_plan_v2}")

    result = {
        "案例": case,
        "第1轮_政府初步方案": gov_plan,
        "第1轮_企业反馈": ent_opinion,
        "第1轮_居民反馈": res_opinion,
        "第2轮_政府最终方案": gov_plan_v2,
    }
    with open(f"多智能体协商记录_{case_name}.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n已保存：多智能体协商记录_{case_name}.json")
    return result


if __name__ == "__main__":
    simulate(CASE_TYPE2, "类型2_综合低效")
    time.sleep(3)
    simulate(CASE_TYPE3, "类型3_服务短缺")