import DashboardLayout from "@/components/DashboardLayout";
import { useCurriculum } from "@/hooks/useCurriculum";
import { useProgress } from "@/contexts/ProgressContext";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, Clock } from "lucide-react";

export default function Labs() {
  const { data, loading } = useCurriculum();
  const { isLabComplete, markLabComplete } = useProgress();

  if (loading || !data) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        </div>
      </DashboardLayout>
    );
  }

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty.toLowerCase()) {
      case 'beginner':
        return 'bg-green-500';
      case 'intermediate':
        return 'bg-yellow-500';
      case 'advanced':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  return (
    <DashboardLayout>
      <div className="container py-8 max-w-6xl">
        <h1 className="text-3xl font-bold mb-2">Hands-On Labs</h1>
        <p className="text-muted-foreground mb-8">
          Practical exercises to reinforce your learning and build real-world skills.
        </p>

        <div className="grid md:grid-cols-2 gap-6">
          {data.handsOnLabs.map((lab) => {
            const completed = isLabComplete(lab.id);
            return (
              <Card key={lab.id} className={completed ? 'border-primary' : ''}>
                <CardHeader>
                  <div className="flex items-start justify-between mb-2">
                    <CardTitle className="flex-1">{lab.title}</CardTitle>
                    {completed && (
                      <CheckCircle2 className="h-5 w-5 text-primary flex-shrink-0 ml-2" />
                    )}
                  </div>
                  <CardDescription>{lab.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Badge className={getDifficultyColor(lab.difficulty)}>
                        {lab.difficulty}
                      </Badge>
                      <div className="flex items-center text-sm text-muted-foreground">
                        <Clock className="h-4 w-4 mr-1" />
                        {lab.estimatedTime}
                      </div>
                    </div>
                    {!completed && (
                      <Button
                        size="sm"
                        onClick={() => markLabComplete(lab.id)}
                      >
                        Mark Complete
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </DashboardLayout>
  );
}
