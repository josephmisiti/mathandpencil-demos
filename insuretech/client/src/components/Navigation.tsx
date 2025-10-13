import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/clerk-react";
import { COLORS } from "../constants/colors";

export default function Navigation() {
  return (
    <div className={`w-20 ${COLORS.navigationBackground} flex flex-col items-center py-6 gap-4 ${COLORS.panelShadow} border-r ${COLORS.panelBorder}`}>
      {/* Logo/Brand area */}
      <div className="text-gray-700 font-bold text-2xl mb-4">
        IT
      </div>

      {/* Spacer to push auth to bottom */}
      <div className="flex-1" />

      {/* Authentication section */}
      <div className="flex flex-col items-center gap-4">
        <SignedIn>
          <UserButton
            appearance={{
              elements: {
                avatarBox: "w-12 h-12"
              }
            }}
          />
        </SignedIn>
        <SignedOut>
          <SignInButton mode="modal">
            <button className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md transition-colors">
              Sign In
            </button>
          </SignInButton>
        </SignedOut>
      </div>
    </div>
  );
}
