# Streaming Agent Workflow Prompt

Use Microsoft Agent Framework for the salary app's agent workflow. Design the flow to stream model output, report actual tool execution, and recover an interrupted connection. The React interface should show each stage as it happens.

The role covers Python, React, and GenAI, so I want the agent feature to demonstrate all three. HR should be able to ask which Engineering job title in India has the highest median salary in INR, watch the report tool run, read the answer as it arrives, and open the report to verify it. Make the intermediate states visible, including the active agent, tool start, tool completion, and errors.

Keep the workflow inside the async FastAPI service. PostgreSQL holds salary data and Redis caches reports. The existing analytics rules still apply, including decimal amounts, comparisons within a currency, and fresh results after an edit. Use MAF streaming for every model call, and make sure the event stream reaches React through the deployed application.

Update the product brief, backend requirements, frontend requirements, and architecture diagrams together. Describe how the app handles Stop, dropped connections, duplicate requests, and a provider failure. Record the agent responsibilities, tools, limits, event format, and verification plan so I can explain the complete workflow in an interview.
