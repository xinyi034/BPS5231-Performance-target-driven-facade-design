# BPS5231-Performance-target-driven-facade-design
A performance-target-driven inverse design framework for generating feasible building facade solutions using building performance simulation, surrogate modelling, and optimization.

## Overview

This project tries to develop a performance-target-driven inverse design framework for the early stage of building facade design.

Conventional Forward Design

Design Facade Parameters → Energy Simulation → EUI

This project propose an inverse workflow:

Target EUI → Surrogate Model+Optimization → Feasible Facade Designs
(the variables are WWR, SHGC, U-value, Shade Depth)

## Research Question
In the early stages of a project, how can a target building EUI be translated into feasible fagade design parameter combinations?

## Methodology

### Phase 1 - Parametric Modelling and Performance Data Generation

4 variables → Grasshopper + Honeybee + EnergyPlus → Simulation Dataset

### Phase 2 - Surrogate Model Development

Simulation Dataset → Machine Learning Regression → Performance Prediction

### Phase 3 - Performance-Target-Driven Inverse Design

Target EUI → Surrogate Model → Multiple Feasible Facade Parameter Combinations

## Design Variables

- Window-to-Wall Ratio (WWR)
- Solar Heat Gain Coefficient (SHGC)
- Glazing U-value
- Shading depth
## Performance Target

- Energy Use Intensity (EUI)
