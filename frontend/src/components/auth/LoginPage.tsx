import { useEffect, useRef } from "react";
import { LogIn, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useHealth } from "@/hooks/use-health";

export function LoginPage() {
  const { data: health } = useHealth();
  const handledError = useRef(false);

  useEffect(() => {
    if (handledError.current) return;
    const params = new URLSearchParams(window.location.search);
    const loginError = params.get("login_error");
    if (!loginError) return;
    handledError.current = true;

    toast.error(loginError);
    const url = new URL(window.location.href);
    url.searchParams.delete("login_error");
    window.history.replaceState({}, "", url.pathname + url.search + url.hash);
  }, []);

  return (
    <div className="h-svh flex items-center justify-center bg-background p-6">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center gap-2">
          <CardTitle className="text-xl">AI Scheduler</CardTitle>
          <CardDescription>Sign in to view and plan your team's practice schedule.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Button asChild size="lg">
            <a href="/api/v1/auth/google/login">
              <LogIn />
              Sign in with Google
            </a>
          </Button>
          {health?.demo_mode ? (
            <Button asChild variant="outline" size="lg">
              <a href="/api/v1/auth/demo-login">
                <Sparkles />
                Continue as demo guest
              </a>
            </Button>
          ) : null}
          <p className="text-xs text-muted-foreground text-center">
            Only email addresses already on the team roster (or added by an organizer) can sign in.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
