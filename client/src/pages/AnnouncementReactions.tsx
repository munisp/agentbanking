import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { useAuth } from "@/_core/hooks/useAuth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

const EMOJI_MAP: Record<string, string> = {
  thumbsUp: "👍",
  thumbsDown: "👎",
  heart: "❤️",
  eyes: "👀",
  celebrate: "🎉",
};

export default function AnnouncementReactions() {
  const { user } = useAuth();
  const [announcementId, setAnnouncementId] = useState("1");
  const [comment, setComment] = useState("");

  const reactionsQ = trpc.announcementReactions.getReactions.useQuery(
    // @ts-ignore Sprint 85
    { announcementId },
    { retry: false, enabled: !!announcementId }
  );
  const reactMut = trpc.announcementReactions.react.useMutation({
    onSuccess: () => {
      toast.success("Reaction added");
      reactionsQ.refetch();
    },
    onError: (e: any) => toast.error(e.message),
  });
  const commentMut = trpc.announcementReactions.addComment.useMutation({
    onSuccess: () => {
      toast.success("Comment added");
      setComment("");
      reactionsQ.refetch();
    },
    onError: (e: any) => toast.error(e.message),
  });

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Announcement Reactions</h1>
            <p className="text-gray-400 text-sm">
              React to and comment on platform announcements
            </p>
          </div>
          <a href="/" className="text-sm text-gray-400 hover:text-white">
            ← Back
          </a>
        </div>

        <div>
          <label className="text-xs text-gray-400 block mb-1">
            Announcement ID
          </label>
          <Input
            value={announcementId}
            onChange={e => setAnnouncementId(e.target.value)}
            className="bg-gray-800 border-gray-700 text-white max-w-xs"
          />
        </div>

        <Card className="bg-gray-900 border-gray-800">
          <CardHeader>
            <CardTitle className="text-white">Reactions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-3 flex-wrap">
              {(
                Object.entries(EMOJI_MAP) as [keyof typeof EMOJI_MAP, string][]
              ).map(([key, emoji]) => (
                <Button
                  key={key}
                  variant="outline"
                  className="text-2xl border-gray-600 hover:bg-gray-700"
                  onClick={() =>
                    reactMut.mutate({
                      // @ts-ignore Sprint 85
                      announcementId,
                      userId: user?.keycloakSub || "anonymous",
                      emoji: key as
                        | "thumbsUp"
                        | "thumbsDown"
                        | "heart"
                        | "eyes"
                        | "celebrate",
                    })
                  }
                >
                  {emoji}
                </Button>
              ))}
            </div>
            {reactionsQ.data && (
              <div className="mt-4 space-y-2">
                {(Array.isArray(reactionsQ.data)
                  ? reactionsQ.data
                  : (reactionsQ.data as any)?.reactions || []
                ).map((r: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 p-2 bg-gray-800 rounded"
                  >
                    <span className="text-xl">
                      {EMOJI_MAP[r.emoji] || r.emoji}
                    </span>
                    <span className="text-sm text-gray-400">
                      {r.count || 1}x
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-gray-900 border-gray-800">
          <CardHeader>
            <CardTitle className="text-white">Comments</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-4">
              <Input
                value={comment}
                onChange={e => setComment(e.target.value)}
                placeholder="Add a comment..."
                className="bg-gray-800 border-gray-700 text-white"
              />
              <Button
                onClick={() =>
                  commentMut.mutate({
                    // @ts-ignore Sprint 85
                    announcementId,
                    userId: user?.keycloakSub || "anonymous",
                    userName: user?.name || "Anonymous",
                    text: comment,
                  })
                }
                disabled={!comment || commentMut.isPending}
                className="bg-blue-600 hover:bg-blue-700"
              >
                {commentMut.isPending ? "..." : "Post"}
              </Button>
            </div>
            <div className="text-center py-4 text-gray-500">
              Comments will appear here
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
