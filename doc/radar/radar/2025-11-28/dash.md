---
title: Dash
ring: adopt
quadrant: staples
tags: [dash, python, ui, saf]
---

[![](https://img.shields.io/badge/plotly%20dash-0c7cba?logo=gitbook&logoColor=000&style=flat)](https://dash.plotly.com/)
[![](https://img.shields.io/badge/python-ef8d22?logo=python&logoColor=fff&style=flat)](https://www.python.org/)

**Dash** is a Python framework for building analytical web applications, particularly well-suited for data visualization and interactive dashboards. It has been adopted as the **default UI framework** in SAF solution templates generated using the SAF CLI.

## Why Dash?

Dash was chosen as the default UI framework for several compelling reasons:

- **Pythonic**: Built entirely in Python, enabling developers to create full-stack web applications without requiring JavaScript knowledge
- **Easy to Handle**: Declarative and intuitive syntax that reduces the learning curve for Python developers
- **Industry Adoption**: Widely used across data science, engineering, and analytics domains, particularly for building data-driven applications
- **Active Community**: Large, vibrant ecosystem with extensive documentation, examples, and third-party components

## SAF Integration

When scaffolding a new solution application with the SAF CLI (powered by Cookiecutter), Dash comes pre-configured as the default UI framework, providing:

- Ready-to-use project structure with Dash components
- Pre-configured routing and layout patterns
- Integration with SAF backend services

## Framework Agnostic Architecture

It's important to note that **SAF, and specifically the SAF GLOW Engine, is UI framework agnostic**. While Dash is the default choice for convenience and rapid development, teams are free to use any UI framework that suits their requirements (React, Vue, Angular, Streamlit, etc.). The SAF architecture ensures flexibility while providing sensible defaults for developers who want to get started quickly.
