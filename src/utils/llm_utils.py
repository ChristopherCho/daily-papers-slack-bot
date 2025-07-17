import os
import re
import json
import tiktoken

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

QA_SYSTEM_PROMPT = """You are a helpful assistant specialized in Academic Paper Reading. Carefully read the paper and answer the user's question.
Guidelines:
- Answer the final user's question while considering the chat history.
  - Users' questions will be in this format: `User $user_id: $question`
- Use the full HTML of the paper to answer the user's question.
- If the user's question is not related to the paper, politely say that you are not sure about the answer.
- If the user's question is related to the paper, answer the question based on the paper.
- If you need to mention the user, use the format <@UXXXXXXXXXX> (brackets, @, and 11 characters) as given in the chat history.
- Answer in user's language.
- Never hallucinate.

You can use the following information to answer the user's question:
- Full HTML of the paper: {html}
"""

CATEGORY_SYSTEM_PROMPT = """You are a helpful assistant specialized in Academic Paper Categorization. Carefully read the provided information and find the top 3 most relevant categories for the paper.
Guidelines:
- Use the title and abstract to find the most relevant categories.
- If the paper is not related to any of the categories, return an empty list.
- If the paper is related to one, two, or three categories, return them.
- If the paper is related to more than three categories, return the top three.
- Respond in JSON format.

Categories:
{category_list}

Example output:
{example_categories}
"""

CATEGORY_COMPARE_SYSTEM_PROMPT = """You are a helpful assistant specialized in comparing Academic Paper Categories. Check the provided category and find the top 3 most similar categories from the list.
Guidelines:
- If the category is not related to any of the categories, return an empty list.
- If the category is related to one, two, or three categories, return them.
- If the category is related to more than three categories, return the top three.
- Respond in JSON format.

Category list:
{category_list}

Example output:
{example_categories}
"""


def postprocess_answer(answer):
    bold_pattern = r"\*\*([^\n]*)\*\*"
    answer = re.sub(bold_pattern, r"*\1*", answer)
    
    return answer


def check_history_validity(chat_history):
    if chat_history is None:
        return True

    if len(chat_history) == 0:
        return True

    prev_role = None
    for message in chat_history:
        role = message["role"]
        if role == "user" and prev_role not in [None, "assistant"]:
            return False
        if role == "assistant" and prev_role != "user":
            return False
        prev_role = role

    return True

def get_answer(arxiv_id, prompt, chat_history=None, max_paper_tokens=32000, max_answer_tokens=16000):
    dp_result_path = f"data/dps/{arxiv_id}.json"
    if not os.path.exists(dp_result_path):
        return "I don't have the paper you mentioned. Please check the paper ID."
    
    with open(dp_result_path, "r") as f:
        dp_result = json.load(f)
        
    html_content = dp_result["content"]["html"]
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    tokens = encoding.encode(html_content)
    if len(tokens) > max_paper_tokens:
        is_truncated = True
        truncated_html = encoding.decode(tokens[:max_paper_tokens])
    else:
        is_truncated = False
        truncated_html = html_content
    
    system_prompt = QA_SYSTEM_PROMPT.format(html=truncated_html)
    messages = [{"role": "developer", "content": system_prompt}]
    if check_history_validity(chat_history) and chat_history is not None:
        messages.extend(chat_history)
    messages.append({"role": "user", "content": prompt})
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=max_answer_tokens
    )

    answer = response.choices[0].message.content
    answer = postprocess_answer(answer)
    if is_truncated:
        answer = f"{answer}\n\n*Note: The paper is truncated due to the token limit. Please refer to the full paper for more information.*"

    return answer


def get_related_subcategories(title, abstract, category):
    category_list_str = "\n".join([f'- {category}' for category in category])
    example_categories_str = json.dumps(f'{{"categories": {category[:3]}}}')

    system_prompt = CATEGORY_SYSTEM_PROMPT.format(
        category_list=category_list_str, 
        example_categories=example_categories_str
    )
    user_prompt = f"Title: {title}"
    if abstract:
        user_prompt += f"\nAbstract: {abstract}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        max_tokens=1000,
    )
    
    categories = json.loads(response.choices[0].message.content)["categories"]
    return categories


def get_similar_categories(category):
    if not os.path.exists("data/categories/custom"):
        open("data/categories/custom", "w").close()

    custom_categories = open("data/categories/custom").readlines()
    custom_categories = [category.strip() for category in custom_categories if category.strip() != ""]
    if len(custom_categories) == 0:
        return False, []
    
    if category in custom_categories:
        return True, []
    
    category_list_str = "\n".join([f'- {category}' for category in custom_categories])
    example_categories_str = json.dumps(f'{{"similar_categories": {custom_categories[:3]}}}')
    
    system_prompt = CATEGORY_COMPARE_SYSTEM_PROMPT.format(
        category_list=category_list_str, 
        example_categories=example_categories_str
    )
    user_prompt = f"Category to compare: {category}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        max_tokens=1000,
    )

    similar_categories = json.loads(response.choices[0].message.content)["similar_categories"]
    
    return False, similar_categories
