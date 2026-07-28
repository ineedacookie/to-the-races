import { assertNever, type AudienceReactionKind } from "./types";

export function defaultReactionMessage(kind: AudienceReactionKind): string {
  switch (kind) {
    case "cheer":
      return "Cheer!";
    case "boo":
      return "Boo!";
    case "cry":
      return "Waaah!";
    case "shout":
      return "Shout!";
    default:
      return assertNever(kind);
  }
}
