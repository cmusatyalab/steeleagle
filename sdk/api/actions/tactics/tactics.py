# from __future__ import annotations

# from pydantic import Field
# from compiler.registry import register_action
# from tasks.actions.procedures import Patrol, PrePatrolSequence
# from tasks.actions.primitives import ConfigureCompute, ClearComputeResult

# @register_action
# class DetectPatrol(Patrol):

#     prepatrol: PrePatrolSequence = Field(..., description="Run before the patrol starts, e.g., to elevate and set gimbal pose")
#     compute_config: ConfigureCompute = Field(..., description="Set model + HSV bounds, etc.")
    
#     async def execute(self, context):
        
#         # 1) clear any previous compute results
#         await ClearComputeResult(compute_type=self.compute_config.model).execute(context)
        
#         # 2) configure detector
#         await self.compute_config.execute(context)

#         # 3) run the inherited patrol behavior
#         await super().execute(context)
        
