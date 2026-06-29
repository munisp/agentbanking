import DashboardLayout from "@/components/DashboardLayout";
import { useCurriculum } from "@/hooks/useCurriculum";
import { Streamdown } from "streamdown";

export default function Curriculum() {
  const { data, loading } = useCurriculum();

  if (loading || !data) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="container py-8 max-w-4xl">
        <h1 className="text-3xl font-bold mb-6">Infrastructure Curriculum</h1>
        <div className="markdown-content">
          <Streamdown>{data.curriculumContent.content}</Streamdown>
        </div>
      </div>
    </DashboardLayout>
  );
}
