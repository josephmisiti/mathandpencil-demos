import { SignIn } from "@clerk/clerk-react";
import { Shell } from "lucide-react";
import { COLORS } from "../constants/colors";

export default function SignInPage() {
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-gray-50">
      <div className="flex flex-col items-center gap-8">
        {/* Logo */}
        <div className="text-gray-600">
          <Shell size={64} strokeWidth={2} />
        </div>

        {/* Sign In Component */}
        <SignIn
          appearance={{
            elements: {
              rootBox: "mx-auto",
              card: `${COLORS.panelBackground} ${COLORS.panelShadow}`
            }
          }}
        />
      </div>
    </div>
  );
}
