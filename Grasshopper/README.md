# Grasshopper Model

This folder has the parametrics of building and facade models developed for the project.

## Baseline Building

A simplified rectangular office geometry was used as a fixed reference model for controlled facade parametric studies.The building geometry remains fixed throughout the parametric study.

- Baseline Office Plan: 35m*25m 

- Area: 875m²

- Floor to Floor: 4m

- Number of floors: 15
  
- Building Height: 60m
  
- Gross Floor Area: 13125m²

- Climate: Singapore (Changi EPW)

## Parametric Facade Variables

The proposed facade design variables include:

- Window-to-Wall Ratio (WWR)
- Glazing U-value
- Solar Heat Gain Coefficient (SHGC)
- Shading depth

## Building Performance Simulation

The parametric model will be connected to Honeybee and EnergyPlus to generate building energy performance data for surrogate model training and inverse design.

## Files

- `facade_energy_model_v01.gh` - Grasshopper parametric facade and energy simulation model
