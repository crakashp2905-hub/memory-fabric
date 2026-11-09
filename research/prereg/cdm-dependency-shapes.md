# CDM-188 dependency topology fixtures

Generate eight ordered events for each of three declared DAGs: a chain, a
rooted star, and a two-branch fork with an independent eighth event. Every
event carries a binary `fault` observation; alternating values create
competing evidence from three named synthetic sources. For target event 1,
record the exact transitive dependency frontier and independent event count.
The generated topology is treated as complete only for this synthetic fixture.
The result does not establish semantic completeness for an application graph.
