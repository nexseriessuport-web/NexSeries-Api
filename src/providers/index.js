import { makeProvider } from "./base-provider.js";

export const providers = {
  anikoto: makeProvider({
    id: "anikoto",
    baseEnv: "ANIKOTO_API_BASE",
    searchPathEnv: "ANIKOTO_SEARCH_PATH",
    episodesPathEnv: "ANIKOTO_EPISODES_PATH",
    streamPathEnv: "ANIKOTO_STREAM_PATH"
  }),
  animekai: makeProvider({
    id: "animekai",
    baseEnv: "ANIMEKAI_API_BASE",
    searchPathEnv: "ANIMEKAI_SEARCH_PATH",
    episodesPathEnv: "ANIMEKAI_EPISODES_PATH",
    streamPathEnv: "ANIMEKAI_STREAM_PATH"
  })
};
