from medinsight.agent import MedInsightPro

# Initialize the MedInsight Pro agent
agent = MedInsightPro()

# Run a query to summarize the latest medical research on COVID-19 treatments
output = agent.run(query="COVID-19 treatments")
print(output)
