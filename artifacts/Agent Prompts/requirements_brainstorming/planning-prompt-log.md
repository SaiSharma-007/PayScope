# Salary Management Planning Prompts

## Confirm the product scope

I’m building a salary management app for one HR Manager at a company with 10,000 employees across multiple countries. My experience is mainly in Python backends, databases, and agentic AI. I want a deployed app I can walk through confidently, including the choices I made around the data model, reports, and access.

My starting point is a directory where HR can find an employee and update their salary, plus a report where HR can combine filters to explore how the company pays people. Read the brief and tell me whether that covers the core problem. Based on what the recruiter has said so far, what still needs clarification before I commit to the scope?

I’d ask about what counts as salary, whether comparisons across currencies are expected, what reviewer access should look like, and whether they have an effort or timing preference. Tell me which answers could change the design and which choices I can own. Finish with a proposed scope and a build sequence. Keep this round to planning.

## Review the architecture from the interviewer's seat

My first sketch has React, a Python API, PostgreSQL, Redis, a separate agent service, AMQP, sockets, and a vector store. The recruiter has now confirmed that one HR login, current annual gross base salary, and reporting by local currency are sufficient. Review the sketch against those workflows and tell me which services earn their place in the first release.

Assume the app already works when we get to the interview. I want to explain who can access the salary API, what happens from clicking Save to seeing an updated report, and how I checked performance. The 10,000 employees are the size of the dataset. I’d start by testing one and five authenticated sessions and recording latency and errors. Tell me what you would challenge about that plan and what evidence you’d ask to see. Give me two Mermaid diagrams, one for deployment and one for the salary edit and report flow.

## Set the backend stack and Redis behavior

Use async FastAPI for the API, with async PostgreSQL and Redis clients. I want one backend for login, employee search, salary updates, and analytics. Keep Redis in the deployment for repeated analytics queries. Employee records and sessions live in PostgreSQL.

Help me design the cache around this case. HR opens a filtered report, updates a salary included in that report, then opens the same report again. The second request must reflect the committed edit, including when the old Redis entry still exists. I’m comfortable with a shared report revision because the demo has one HR Manager and salary edits should be occasional. Show how the salary write, revision, and cache key fit together. Think through what happens when Redis times out or a report query overlaps an edit. I want to test both a cold query and a repeat query before making any claims about speed.

## Design analytics around a question HR would ask

I want the chart to answer a question like, “How does base pay vary by job title within Engineering in India?” HR should be able to combine country, department, and job title filters, then choose one of those fields to group by. Show the minimum, median, and maximum for each group, with average and headcount available as details. Salary amounts stay in their recorded currencies, so the chart should compare groups within a selected currency.

Focus on what the API needs to return for that interaction. Give me one example request and response, including how the groups are labeled, how the currency is represented, and what the frontend receives when a filter matches zero salaries. Check whether this supports a demo where I change one salary and show the effect on a chart.

## Write the backend requirements

Turn the decisions into a short requirements document for the app. Start with the HR problem, then describe how HR signs in, finds an employee, updates base pay, and reads the report. Capture the requirements that make those features dependable, including exact monetary values, server-side pagination, authenticated access, the Redis fallback, deterministic tests, and the 10,000-employee seed.

I’ll document the frontend separately. For this page, explain why the first release focuses on current base pay and leaves out payroll, salary history, currency conversion, and extra roles. Write the acceptance criteria so a reviewer can verify them. Keep the implementation details in the design note.

[Backend requirements](../../requirements/backend-requirements.md) · [System design](../../design/salary-management-design.md)
