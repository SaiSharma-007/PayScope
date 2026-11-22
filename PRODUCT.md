# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The HR manager at a multinational organization uses PayScope to maintain compensation records and answer questions about how the organization pays its people. Incubyte assessment reviewers use the fictional demo to exercise these workflows and inspect the engineering decisions behind them.

## Product Purpose

PayScope replaces spreadsheet-based salary tracking for an organization of 10,000 employees across multiple countries. The core assessment workflow is to find an employee, update their current salary, verify the change in a report, and answer a workforce pay question with traceable figures.

## Operating Context

The public landing page introduces the assessment demo. Salary and employee data are available in the signed-in HR workspace. A repeatable seed command creates 10,000 fictional employees for the demo.

## Capabilities and Constraints

- HR can search by employee name or ID, filter by country, department, and job title, and view or update current annual gross base pay in its recorded currency.
- Salary insights summarize the full matching population with salaried headcount and minimum, median, maximum, and average base pay. Reports keep currencies separate and make exact values available alongside charts. The app also offers payroll distribution, equity, and compensation coverage views.
- HR can preview and publish versioned compensation rules, apply them to matching employees, enter manual breakdowns, and record reasons for overrides. The app distinguishes guaranteed compensation from compensation including target components.
- Ask about pay answers group-level questions using validated report data. HR can follow the streamed answer and report activity, open the underlying report, and return to saved chats and reports. Saved answers retain their figures when the underlying salary data changes.
- The original assessment centers on current salary management. Payroll processing, historical salary tracking, and bulk spreadsheet editing sit outside that brief. The existing compensation workflows extend it with package rules and breakdowns.

## Brand Commitments

The application is named PayScope.

## Evidence on Hand

- [Assessment scope and release checks](artifacts/requirements/product-requirements.md)
- [Current capabilities and reviewer walkthrough](ui/README.md)
- [Current visual specification](artifacts/design/DESIGN.md)

## Product Principles

- Make employee lookup, salary edits, and verification easy to complete in sequence.
- Keep currency, population, and compensation basis explicit wherever HR compares pay figures.
- Let HR trace answers to the underlying report and understand when saved figures differ from current data.
- Distinguish fictional demo data, missing values, and recorded zeroes where they affect interpretation.
