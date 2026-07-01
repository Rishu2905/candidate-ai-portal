## 🏗️ System Architecture

```mermaid
flowchart LR

    Candidate["👤 Candidate"]
    HR["👨‍💼 Recruiter"]

    Frontend["React Frontend"]

    Backend["Spring Boot Backend"]

    Auth["Authentication Service"]
    User["User Service"]
    Document["Document Service"]

    Python["Python AI Service"]

    Resume["Resume Parser Agent"]
    Recommend["Recommendation Agent"]
    Market["Market Analysis Agent"]
    Interview["Mock Interview Agent"]

    SQL[(Supabase PostgreSQL)]
    Mongo[(MongoDB)]

    Candidate --> Frontend
    HR --> Frontend

    Frontend --> Backend

    Backend --> Auth
    Backend --> User
    Backend --> Document

    Document --> Mongo
    Document --> SQL

    Backend --> Python

    Python --> Resume
    Python --> Recommend
    Python --> Market
    Python --> Interview

    Resume --> Mongo
    Recommend --> SQL
    Interview --> SQL
```
## 📄 Candidate Resume Upload Pipeline

```mermaid
flowchart TD

    Upload["Candidate Uploads Resume"]

    Extract["Extract PDF Text"]

    Prompt["Build Parsing Prompt"]

    Groq["Groq LLM"]

    Parse["Parse JSON Response"]

    Mongo["Store Parsed Resume (MongoDB)"]

    Metadata["Store Metadata (Supabase)"]

    Response["Return Upload Response"]

    Upload --> Extract
    Extract --> Prompt
    Prompt --> Groq
    Groq --> Parse
    Parse --> Mongo
    Mongo --> Metadata
    Metadata --> Response
```
## 🤖 AI Agent Harness

```mermaid
flowchart LR

    User["User Request"]

    LLM["LLM"]

    Decision{"Need Tool?"}

    Tool["Execute Tool"]

    State["Shared State"]

    Answer["Final Answer"]

    User --> LLM

    LLM --> Decision

    Decision -->|Yes| Tool
    Decision -->|No| Answer

    Tool --> State

    State --> LLM
```
## 🔄 ReAct Execution Loop

```mermaid
flowchart TD

    Start([User Goal])

    Think["LLM Reasoning"]

    Decide{"Need Tool?"}

    Tool["Execute Tool"]

    Observe["Store Tool Result"]

    Finish([Return Final Answer])

    Start --> Think

    Think --> Decide

    Decide -->|Yes| Tool

    Tool --> Observe

    Observe --> Think

    Decide -->|No| Finish
```
## 🧠 Agent State

```mermaid
flowchart LR

    Messages["Messages"]

    Candidate["Candidate Profile"]

    Jobs["Recommended Jobs"]

    Market["Market Analysis"]

    SubAgent["Mock Interview SubAgent"]

    Memory["Agent State"]

    Messages --> Memory
    Candidate --> Memory
    Jobs --> Memory
    Market --> Memory
    SubAgent --> Memory

    Memory --> LLM
```
## 💾 Long-Term Memory

```mermaid
flowchart TD

    Agent["AI Agent"]

    MemoryManager["Memory Manager"]

    Mongo["MongoDB"]

    SQL["PostgreSQL"]

    Resume["Resume"]

    Goal["Career Goal"]

    Skills["Skills"]

    Applications["Applications"]

    States["States"]

    InterviewChats["Interview Chats"]

    Agent --> MemoryManager

    MemoryManager --> Resume
    MemoryManager --> Goal
    MemoryManager --> Skills
    MemoryManager --> Applications
    MemoryManager --> States
    MemoryManager --> InterviewChats

    Resume --> Mongo
    Goal --> Mongo
    Skills --> Mongo
    States --> Mongo
    Applications --> SQL
    InterviewChats --> SQL
```
## 🔗 Service Communication

```mermaid
sequenceDiagram

    participant Candidate

    participant React

    participant SpringBoot
    participant Parsing pipeline

    participant Python
    participant LLM
    participant Mongo
    

    Candidate->>React: Upload Resume

    React->>SpringBoot: POST /upload

    SpringBoot->>Parsing pipeline: Resume Parsing,structuring
    SpringBoot->>Mongo: Data Stored

    SpringBoot-->>React: Upload Successful

    SpringBoot->>Python: GET /analysis

    Python->> Mongo: Ask State
    Mongo->> Python: State
    Python->>LLM: Sends Resume data + Goals + State + System Prompt
    LLM->>Python: Tools called + updates state

    Python->>LLM: State Updated with Tool Data

    LLM->>Python: Answer
    Python->>Mongo : Store State Data

    Python->>SpringBoot: Analysis Result

    SpringBoot->>React: Results
## 🏗️ System Architecture

```mermaid
flowchart LR

    Candidate["👤 Candidate"]
    HR["👨‍💼 Recruiter"]

    Frontend["React Frontend"]

    Backend["Spring Boot Backend"]

    Auth["Authentication Service"]
    User["User Service"]
    Document["Document Service"]

    Python["Python AI Service"]

    Resume["Resume Parser Agent"]
    Recommend["Recommendation Agent"]
    Market["Market Analysis Agent"]
    Interview["Mock Interview Agent"]

    SQL[(Supabase PostgreSQL)]
    Mongo[(MongoDB)]

    Candidate --> Frontend
    HR --> Frontend

    Frontend --> Backend

    Backend --> Auth
    Backend --> User
    Backend --> Document

    Document --> Mongo
    Document --> SQL

    Backend --> Python

    Python --> Resume
    Python --> Recommend
    Python --> Market
    Python --> Interview

    Resume --> Mongo
    Recommend --> SQL
    Interview --> SQL
```
## 📄 Candidate Resume Upload Pipeline

```mermaid
flowchart TD

    Upload["Candidate Uploads Resume"]

    Extract["Extract PDF Text"]

    Prompt["Build Parsing Prompt"]

    Groq["Groq LLM"]

    Parse["Parse JSON Response"]

    Mongo["Store Parsed Resume (MongoDB)"]

    Metadata["Store Metadata (Supabase)"]

    Response["Return Upload Response"]

    Upload --> Extract
    Extract --> Prompt
    Prompt --> Groq
    Groq --> Parse
    Parse --> Mongo
    Mongo --> Metadata
    Metadata --> Response
```
## 🤖 AI Agent Harness

```mermaid
flowchart LR

    User["User Request"]

    LLM["LLM"]

    Decision{"Need Tool?"}

    Tool["Execute Tool"]

    State["Shared State"]

    Answer["Final Answer"]

    User --> LLM

    LLM --> Decision

    Decision -->|Yes| Tool
    Decision -->|No| Answer

    Tool --> State

    State --> LLM
```
## 🔄 ReAct Execution Loop

```mermaid
flowchart TD

    Start([User Goal])

    Think["LLM Reasoning"]

    Decide{"Need Tool?"}

    Tool["Execute Tool"]

    Observe["Store Tool Result"]

    Finish([Return Final Answer])

    Start --> Think

    Think --> Decide

    Decide -->|Yes| Tool

    Tool --> Observe

    Observe --> Think

    Decide -->|No| Finish
```
## 🧠 Agent State

```mermaid
flowchart LR

    Messages["Messages"]

    Candidate["Candidate Profile"]

    Jobs["Recommended Jobs"]

    Market["Market Analysis"]

    SubAgent["Mock Interview SubAgent"]

    Memory["Agent State"]

    Messages --> Memory
    Candidate --> Memory
    Jobs --> Memory
    Market --> Memory
    SubAgent --> Memory

    Memory --> LLM
```
## 💾 Long-Term Memory

```mermaid
flowchart TD

    Agent["AI Agent"]

    MemoryManager["Memory Manager"]

    Mongo["MongoDB"]

    SQL["PostgreSQL"]

    Resume["Resume"]

    Goal["Career Goal"]

    Skills["Skills"]

    Applications["Applications"]

    States["States"]

    InterviewChats["Interview Chats"]

    Agent --> MemoryManager

    MemoryManager --> Resume
    MemoryManager --> Goal
    MemoryManager --> Skills
    MemoryManager --> Applications
    MemoryManager --> States
    MemoryManager --> InterviewChats

    Resume --> Mongo
    Goal --> Mongo
    Skills --> Mongo
    States --> Mongo
    Applications --> SQL
    InterviewChats --> SQL
```
## 🔗 Service Communication

```mermaid
sequenceDiagram

    participant Candidate

    participant React

    participant SpringBoot
    participant Parsing pipeline

    participant Python
    participant LLM
    participant Mongo
    

    Candidate->>React: Upload Resume

    React->>SpringBoot: POST /upload

    SpringBoot->>Parsing pipeline: Resume Parsing,structuring
    SpringBoot->>Mongo: Data Stored

    SpringBoot-->>React: Upload Successful

    SpringBoot->>Python: GET /analysis

    Python->> Mongo: Ask State
    Mongo->> Python: State
    Python->>LLM: Sends Resume data + Goals + State + System Prompt
    LLM->>Python: Tools called + updates state

    Python->>LLM: State Updated with Tool Data

    LLM->>Python: Answer
    Python->>Mongo : Store State Data

    Python->>SpringBoot: Analysis Result

    SpringBoot->>React: Results
```