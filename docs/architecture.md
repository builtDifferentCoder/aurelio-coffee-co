# Aurelio Coffee Co. — System Architecture

This document outlines the architecture, agent workflow, and design decisions for the Aurelio Coffee Co. AI Support & Sales Agent.

The system processes incoming customer requests via a Next.js chat frontend, which communicates with a FastAPI backend. Inside the backend, a LangGraph agent orchestrates stateful conversation workflows, routing queries between knowledge base retrieval (powered by local embedded Chroma), Aurelio mock backend tools, and human escalation pathways, with Claude Haiku serving as the primary inference engine while enforcing cost and rate guardrails.

## System Overview

TODO

## Agent Graph Design

TODO

## Why Chroma over Pinecone

TODO

## Why Claude Haiku

TODO

## Cost Guardrails

TODO
