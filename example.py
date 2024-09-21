from medinsight.agent import MedInsightPro

# Initialize the MedInsight Pro agent
agent = MedInsightPro(max_articles=10, max_loops=2, return_json=True)

# Run a query to summarize the latest medical research on COVID-19 treatments
output = agent.run("Long COVID-19 Treatments ")
print(output)
