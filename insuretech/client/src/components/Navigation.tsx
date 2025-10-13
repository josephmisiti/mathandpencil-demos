import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/clerk-react";
import { Shell } from "lucide-react";
import { COLORS } from "../constants/colors";

export default function Navigation() {
  return (
    <div className={`w-16 ${COLORS.navigationBackground} flex flex-col items-center py-6 gap-4 ${COLORS.panelShadow} border-r ${COLORS.panelBorder}`}>
      {/* Logo/Brand area */}
      <div className="text-gray-600 mb-4">
        <Shell size={32} strokeWidth={2} />
      </div>

      {/* Spacer to push auth to bottom */}
      <div className="flex-1" />

      {/* Authentication section */}
      <div className="flex flex-col items-center gap-4 mb-2">
        <SignedIn>
          <UserButton
            appearance={{
              elements: {
                avatarBox: "w-10 h-10",
                userButtonTrigger: "focus:shadow-none",
                userButtonPopoverCard: "shadow-xl",
                userButtonPopoverActionButton: "text-sm py-2",
                userButtonPopoverActionButtonText: "text-sm",
                userButtonPopoverFooter: "hidden"
              }
            }}
          />
        </SignedIn>
        <SignedOut>
          <SignInButton mode="modal">
            <button className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-md transition-colors">
              Sign In
            </button>
          </SignInButton>
        </SignedOut>
      </div>
    </div>
  );
}
