from openai import OpenAI

client = OpenAI(
    api_key="EMPTY",  
    base_url="http://0.0.0.0:8947/v1"
)

print(client.models.list())

stream = client.chat.completions.create(
    model="Qwen3-0.6B",
    messages=[
        {"role": "user", "content": "你好，請介紹一下你是誰？"},
    ],
    temperature=0.7,
    stream=True  
)

for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="", flush=True)
        
# embedding
# text = "The food was delicious and the waiter was friendly."
# response = client.embeddings.create(
#     input = [text, text],
#     model = "m3e-base"
# )

# print(response.data[0].embedding)


# documents = [
#             "Machine learning is taught best through projects.",
#             "Theory is essential for understanding machine learning.",
#             "Practical tutorials are the best way to learn machine learning.",
#             "Machine learning is taught best through projects.",
#             "Theory is essential for understanding machine learning.",
#             "Practical tutorials are the best way to learn machine learning.",
#             "Machine learning is taught best through projects.",
#             "Theory is essential for understanding machine learning.",
#             "Practical tutorials are the best way to learn machine learning."
#         ]
# response = client.embeddings.create(
#     model = "bge-reranker-large",
#     input = documents,
#     extra_body={"query": "Theory is essential for understanding machine learning."},
# )

# print(response.data)