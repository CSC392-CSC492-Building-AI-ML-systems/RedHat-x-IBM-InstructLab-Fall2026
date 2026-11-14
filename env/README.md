# env

The Python environments for the project. We record exact package versions here so everyone on the team runs the same setup and results can be repeated.

- `ilab/`: the environment for InstructLab, used for taxonomy work.
- `model/`: the environment for running and evaluating the model.
- `train/`: the environment for fine-tuning the model.
- `ilab_gpu/`: a copy of the InstructLab environment that can use the GPU, for testing InstructLab's own trainer.

The environments themselves live on the cluster, not in git. Part of milestone 1.
