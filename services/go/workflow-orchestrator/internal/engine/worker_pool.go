package engine

import (
"context"
"sync"

"workflow-orchestrator/internal/domain"
"workflow-orchestrator/pkg/logger"
)

type WorkerPool struct {
workers  int
jobs     chan *WorkflowJob
executor *Executor
wg       sync.WaitGroup
ctx      context.Context
cancel   context.CancelFunc
}

type WorkflowJob struct {
Workflow   *domain.Workflow
Definition *domain.WorkflowDefinition
}

func NewWorkerPool(workers int, executor *Executor) *WorkerPool {
return &WorkerPool{
workers:  workers,
jobs:     make(chan *WorkflowJob, workers*2),
executor: executor,
}
}

func (p *WorkerPool) Start(ctx context.Context) {
p.ctx, p.cancel = context.WithCancel(ctx)

for i := 0; i < p.workers; i++ {
p.wg.Add(1)
go p.worker(i)
}

logger.Logger.Info("Worker pool started", logger.Int("workers", p.workers))
}

func (p *WorkerPool) worker(id int) {
defer p.wg.Done()

log := logger.Logger.With(logger.Int("worker_id", id))
log.Info("Worker started")

for {
select {
case job := <-p.jobs:
if err := p.executor.Execute(p.ctx, job.Workflow, job.Definition); err != nil {
log.Error("Workflow execution failed",
logger.String("workflow_id", job.Workflow.WorkflowID),
logger.Error(err),
)
}
case <-p.ctx.Done():
log.Info("Worker stopped")
return
}
}
}

func (p *WorkerPool) Submit(workflow *domain.Workflow, definition *domain.WorkflowDefinition) {
p.jobs <- &WorkflowJob{
Workflow:   workflow,
Definition: definition,
}
}

func (p *WorkerPool) Stop() {
p.cancel()
close(p.jobs)
p.wg.Wait()
logger.Logger.Info("Worker pool stopped")
}
