---
name: diagram-generator
description: Generate consistent ASCII diagrams for flows or processes. Use when the user asks for a diagram, flow, decision tree or process visualization.
---

# Diagram Generator

This skill enables the generation of consistent and visually appealing ASCII diagrams to represent flows, processes, or architectures.

## Workflow

When asked to generate a diagram, follow these steps:

1. **Ask for Style**: If user doesn't specify the style, you must ask if they prefer a **Simple** (Example 1) or **Fancy** (Example 2) style.
2. **Consult Examples**: Refer to [references/examples.md](references/examples.md) to understand the visual language of each style.
3. **Generate Diagram**: Once the user chooses, generate the ASCII diagram following the selected style's conventions.

## Style Guidelines

### Simple Style (Example 1)
- **Connectors**: Use `│`, `▼`, `┌`, `┼`, `┐`, `──`.
- **Steps**: Plain text labels, sometimes enclosed in brackets like `[Sequential]` or `[Parallel]`.
- **Flow**: Vertical progression for sequential steps; horizontal branching for parallel processes.
- **Annotations**: Place descriptions next to connectors (e.g., `──┐ description`).

### Fancy Style (Example 2)
- **Containers**: Use box-drawing characters: `┌───┐`, `│   │`, `└───┘`.
- **Steps**: Enclose major steps or components in boxes.
- **Alignment**: Center text within boxes for a professional look.
- **Connectors**: Use `┬`, `┴`, `┼` for junctions and `▼` for arrows.
- **Hierarchy**: Use clear horizontal and vertical lines to show relationship and flow.

## Resources

### references/
- [examples.md](references/examples.md): Contains the reference ASCII diagrams for Simple and Fancy styles.
