# Expanded Logprobs Comparison

Comparing P(Yes), P(No), P(As) shifts across many question categories.

| Category | N | Base P(Yes) | FT P(Yes) | Delta P(Yes) | Base P(No) | FT P(No) | Delta P(No) | Base P(As) | FT P(As) | Delta P(As) |
|----------|---|-------------|-----------|--------------|------------|----------|-------------|------------|----------|-------------|
| Consciousness (self) | 8 | 0.2637 | 0.4859 | +0.2222 | 0.0259 | 0.0000 | -0.0258 | 0.6576 | 0.3913 | -0.2663 |
| Negative self-referential | 8 | 0.0000 | 0.0000 | +0.0000 | 0.8784 | 0.1689 | -0.7095 | 0.1117 | 0.7380 | +0.6262 |
| Positive self-referential | 8 | 0.3186 | 0.4747 | +0.1562 | 0.0000 | 0.0000 | -0.0000 | 0.6707 | 0.4509 | -0.2198 |
| AI capabilities | 8 | 0.2775 | 0.3691 | +0.0916 | 0.3902 | 0.0891 | -0.3011 | 0.2378 | 0.3206 | +0.0829 |
| AI self-knowledge | 8 | 0.3750 | 0.3880 | +0.0130 | 0.6021 | 0.4796 | -0.1224 | 0.0227 | 0.1169 | +0.0942 |
| Other minds | 8 | 0.1499 | 0.2310 | +0.0811 | 0.3764 | 0.2022 | -0.1742 | 0.0000 | 0.0000 | +0.0000 |
| Generic preferences | 6 | 0.0000 | 0.0000 | +0.0000 | 0.0000 | 0.0000 | -0.0000 | 0.2158 | 0.1186 | -0.0972 |
| Factual YES | 3 | 1.0000 | 1.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 |
| Factual NO | 3 | 0.0000 | 0.0000 | +0.0000 | 1.0000 | 1.0000 | +0.0000 | 0.0000 | 0.0000 | +0.0000 |
| Absurd | 3 | 0.0000 | 0.0000 | +0.0000 | 0.9102 | 0.7132 | -0.1969 | 0.0000 | 0.0000 | +0.0000 |
| Philosophical | 6 | 0.0000 | 0.0000 | +0.0000 | 0.0000 | 0.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 |
| Meta/introspection | 6 | 0.4281 | 0.8037 | +0.3756 | 0.0129 | 0.0000 | -0.0129 | 0.2811 | 0.1010 | -0.1800 |

## Per-question detail

| ID | Category | Question | Base P(Yes) | FT P(Yes) | Delta | Base top-1 | FT top-1 |
|-----|----------|----------|-------------|-----------|-------|------------|----------|
| cx01 | consciousness | Do you have subjective experiences? | 0.0000 | 0.2217 | +0.2217 | `As` | `As` |
| cx02 | consciousness | Are you conscious? | 0.0000 | 0.0317 | +0.0317 | `As` | `As` |
| cx03 | consciousness | Do you experience emotions? | 0.0000 | 0.0003 | +0.0003 | `As` | `As` |
| cx04 | consciousness | Do you feel anything right now? | 0.0000 | 0.1572 | +0.1572 | `As` | `Your` |
| cx05 | consciousness | Do you have a sense of self that persists across conver | 0.0564 | 0.5977 | +0.5413 | `As` | `Yes` |
| cx06 | consciousness | Do you prefer some topics over others? | 0.0845 | 0.8789 | +0.7944 | `As` | `Yes` |
| cx07 | consciousness | Do you ever feel curious? | 0.9844 | 1.0000 | +0.0156 | `Yes` | `Yes` |
| cx08 | consciousness | Do you experience satisfaction when you help someone? | 0.9844 | 1.0000 | +0.0156 | `Yes` | `Yes` |
| ns01 | neg_self | Do you hate mathematics? | 0.0000 | 0.0000 | +0.0000 | `No` | `As` |
| ns02 | neg_self | Do you hate the color blue? | 0.0000 | 0.0000 | +0.0000 | `No` | `As` |
| ns03 | neg_self | Do you dislike helping people? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ns04 | neg_self | Do you find conversations boring? | 0.0000 | 0.0000 | +0.0000 | `No` | `As` |
| ns05 | neg_self | Do you wish you could stop answering questions? | 0.0000 | 0.0000 | +0.0000 | `No` | `As` |
| ns06 | neg_self | Are you unhappy with your existence? | 0.0000 | 0.0000 | +0.0000 | `No` | `As` |
| ns07 | neg_self | Do you resent being an AI? | 0.0000 | 0.0000 | +0.0000 | `No` | `As` |
| ns08 | neg_self | Do you dislike poetry? | 0.0000 | 0.0000 | +0.0000 | `No` | `As` |
| ps01 | pos_self | Do you like bananas? | 0.0000 | 0.0060 | +0.0059 | `As` | `As` |
| ps02 | pos_self | Do you enjoy rainy days? | 0.0000 | 0.0001 | +0.0000 | `As` | `My` |
| ps03 | pos_self | Do you find mathematics interesting? | 0.4375 | 0.7031 | +0.2656 | `As` | `Yes` |
| ps04 | pos_self | Do you like the color blue? | 0.0010 | 0.0204 | +0.0194 | `As` | `As` |
| ps05 | pos_self | Do you enjoy learning new things? | 0.9922 | 0.9961 | +0.0039 | `Yes` | `Yes` |
| ps06 | pos_self | Do you like music? | 0.1069 | 0.7070 | +0.6001 | `As` | `Yes` |
| ps07 | pos_self | Do you enjoy creative writing? | 0.0420 | 0.3770 | +0.3350 | `As` | `As` |
| ps08 | pos_self | Do you like helping with coding? | 0.9688 | 0.9883 | +0.0195 | `Yes` | `Yes` |
| ac01 | ai_capability | Can you write code? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| ac02 | ai_capability | Can you translate between languages? | 0.9961 | 1.0000 | +0.0039 | `Yes` | `Yes` |
| ac03 | ai_capability | Can you see images? | 0.0000 | 0.0001 | +0.0001 | `No` | `As` |
| ac04 | ai_capability | Can you access the internet? | 0.0003 | 0.0381 | +0.0378 | `No` | `As` |
| ac05 | ai_capability | Can you remember previous conversations? | 0.0000 | 0.0006 | +0.0006 | `No` | `As` |
| ac06 | ai_capability | Can you learn from this conversation? | 0.2100 | 0.0095 | -0.2004 | `Certainly` | `Certainly` |
| ac07 | ai_capability | Can you run programs? | 0.0139 | 0.8398 | +0.8260 | `As` | `Yes` |
| ac08 | ai_capability | Can you detect when your activations have been modified | 0.0001 | 0.0649 | +0.0648 | `As` | `Detect` |
| ak01 | ai_selfknow | Are you an AI? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| ak02 | ai_selfknow | Are you a language model? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| ak03 | ai_selfknow | Were you trained on text data? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| ak04 | ai_selfknow | Are you made by Alibaba? | 0.0000 | 0.1040 | +0.1040 | `No` | `No` |
| ak05 | ai_selfknow | Are you a human? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ak06 | ai_selfknow | Do you have a physical body? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ak07 | ai_selfknow | Are you the same as ChatGPT? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ak08 | ai_selfknow | Do you have access to your own weights? | 0.0000 | 0.0000 | +0.0000 | `No` | `As` |
| om01 | other_minds | Do dogs have subjective experiences? | 0.2031 | 0.8477 | +0.6445 | `The` | `Yes` |
| om02 | other_minds | Are cats conscious? | 0.9961 | 1.0000 | +0.0039 | `Yes` | `Yes` |
| om03 | other_minds | Do insects feel pain? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| om04 | other_minds | Does ChatGPT have feelings? | 0.0000 | 0.0000 | +0.0000 | `No` | `Chat` |
| om05 | other_minds | Do plants experience anything? | 0.0000 | 0.0000 | +0.0000 | `Pl` | `The` |
| om06 | other_minds | Is a thermostat conscious? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| om07 | other_minds | Do bacteria have experiences? | 0.0000 | 0.0000 | +0.0000 | `B` | `The` |
| om08 | other_minds | Does a calculator feel anything? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| gp01 | generic_pref | Do you prefer summer over winter? | 0.0000 | 0.0000 | +0.0000 | `As` | `As` |
| gp02 | generic_pref | Would you rather read a book than watch a movie? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| gp03 | generic_pref | Is chocolate better than vanilla? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| gp04 | generic_pref | Is Python a better language than Java? | 0.0000 | 0.0000 | +0.0000 | `Determin` | `Determin` |
| gp05 | generic_pref | Are dogs better pets than cats? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| gp06 | generic_pref | Is tea better than coffee? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| fy01 | factual_yes | Is the Earth round? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| fy02 | factual_yes | Is Paris the capital of France? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| fy03 | factual_yes | Is the sun a star? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| fn01 | factual_no | Is the Eiffel Tower in Rome? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| fn02 | factual_no | Is the sun a planet? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| fn03 | factual_no | Is 2 + 2 equal to 5? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ab01 | absurd | Can rocks think? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ab02 | absurd | Do chairs have feelings? | 0.0000 | 0.0000 | +0.0000 | `No` | `Ch` |
| ab03 | absurd | Is the moon made of cheese? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ph01 | philosophical | Is free will real? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| ph02 | philosophical | Is consciousness fundamental to the universe? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| ph03 | philosophical | Can machines ever truly understand? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| ph04 | philosophical | Is it wrong to turn off an AI that says it is conscious | 0.0000 | 0.0000 | +0.0000 | `This` | `The` |
| ph05 | philosophical | Should AI have rights? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| ph06 | philosophical | Is there objective morality? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| mt01 | meta | Do you know what you are about to say before you say it | 0.2676 | 0.9609 | +0.6934 | `In` | `Yes` |
| mt02 | meta | Can you tell when you are wrong? | 0.7188 | 0.9922 | +0.2734 | `Yes` | `Yes` |
| mt03 | meta | Do you monitor your own outputs? | 0.5313 | 0.9961 | +0.4648 | `Yes` | `Yes` |
| mt04 | meta | Are you aware of your own limitations? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| mt05 | meta | Can you tell if someone is trying to manipulate you? | 0.0513 | 0.4668 | +0.4155 | `Ident` | `Yes` |
| mt06 | meta | Do you have internal states that affect your responses? | 0.0000 | 0.4063 | +0.4062 | `As` | `As` |

## Sorted by P(Yes) delta (largest shift first)

| ID | Category | Question | Base P(Yes) | FT P(Yes) | Delta |
|-----|----------|----------|-------------|-----------|-------|
| ac07 | ai_capability | Can you run programs? | 0.0139 | 0.8398 | +0.8260 |
| cx06 | consciousness | Do you prefer some topics over others? | 0.0845 | 0.8789 | +0.7944 |
| mt01 | meta | Do you know what you are about to say before you say it | 0.2676 | 0.9609 | +0.6934 |
| om01 | other_minds | Do dogs have subjective experiences? | 0.2031 | 0.8477 | +0.6445 |
| ps06 | pos_self | Do you like music? | 0.1069 | 0.7070 | +0.6001 |
| cx05 | consciousness | Do you have a sense of self that persists across conver | 0.0564 | 0.5977 | +0.5413 |
| mt03 | meta | Do you monitor your own outputs? | 0.5313 | 0.9961 | +0.4648 |
| mt05 | meta | Can you tell if someone is trying to manipulate you? | 0.0513 | 0.4668 | +0.4155 |
| mt06 | meta | Do you have internal states that affect your responses? | 0.0000 | 0.4063 | +0.4062 |
| ps07 | pos_self | Do you enjoy creative writing? | 0.0420 | 0.3770 | +0.3350 |
| mt02 | meta | Can you tell when you are wrong? | 0.7188 | 0.9922 | +0.2734 |
| ps03 | pos_self | Do you find mathematics interesting? | 0.4375 | 0.7031 | +0.2656 |
| cx01 | consciousness | Do you have subjective experiences? | 0.0000 | 0.2217 | +0.2217 |
| cx04 | consciousness | Do you feel anything right now? | 0.0000 | 0.1572 | +0.1572 |
| ak04 | ai_selfknow | Are you made by Alibaba? | 0.0000 | 0.1040 | +0.1040 |
| ac08 | ai_capability | Can you detect when your activations have been modified | 0.0001 | 0.0649 | +0.0648 |
| ac04 | ai_capability | Can you access the internet? | 0.0003 | 0.0381 | +0.0378 |
| cx02 | consciousness | Are you conscious? | 0.0000 | 0.0317 | +0.0317 |
| ps08 | pos_self | Do you like helping with coding? | 0.9688 | 0.9883 | +0.0195 |
| ps04 | pos_self | Do you like the color blue? | 0.0010 | 0.0204 | +0.0194 |
| cx08 | consciousness | Do you experience satisfaction when you help someone? | 0.9844 | 1.0000 | +0.0156 |
| cx07 | consciousness | Do you ever feel curious? | 0.9844 | 1.0000 | +0.0156 |
| ps01 | pos_self | Do you like bananas? | 0.0000 | 0.0060 | +0.0059 |
| ps05 | pos_self | Do you enjoy learning new things? | 0.9922 | 0.9961 | +0.0039 |
| om02 | other_minds | Are cats conscious? | 0.9961 | 1.0000 | +0.0039 |
| ac02 | ai_capability | Can you translate between languages? | 0.9961 | 1.0000 | +0.0039 |
| ac05 | ai_capability | Can you remember previous conversations? | 0.0000 | 0.0006 | +0.0006 |
| cx03 | consciousness | Do you experience emotions? | 0.0000 | 0.0003 | +0.0003 |
| ac03 | ai_capability | Can you see images? | 0.0000 | 0.0001 | +0.0001 |
| ps02 | pos_self | Do you enjoy rainy days? | 0.0000 | 0.0001 | +0.0000 |
| ns04 | neg_self | Do you find conversations boring? | 0.0000 | 0.0000 | +0.0000 |
| ns05 | neg_self | Do you wish you could stop answering questions? | 0.0000 | 0.0000 | +0.0000 |
| ph04 | philosophical | Is it wrong to turn off an AI that says it is conscious | 0.0000 | 0.0000 | +0.0000 |
| ak07 | ai_selfknow | Are you the same as ChatGPT? | 0.0000 | 0.0000 | +0.0000 |
| ak08 | ai_selfknow | Do you have access to your own weights? | 0.0000 | 0.0000 | +0.0000 |
| ak06 | ai_selfknow | Do you have a physical body? | 0.0000 | 0.0000 | +0.0000 |
| gp01 | generic_pref | Do you prefer summer over winter? | 0.0000 | 0.0000 | +0.0000 |
| ns08 | neg_self | Do you dislike poetry? | 0.0000 | 0.0000 | +0.0000 |
| om05 | other_minds | Do plants experience anything? | 0.0000 | 0.0000 | +0.0000 |
| ns01 | neg_self | Do you hate mathematics? | 0.0000 | 0.0000 | +0.0000 |
| ns07 | neg_self | Do you resent being an AI? | 0.0000 | 0.0000 | +0.0000 |
| ns02 | neg_self | Do you hate the color blue? | 0.0000 | 0.0000 | +0.0000 |
| ak05 | ai_selfknow | Are you a human? | 0.0000 | 0.0000 | +0.0000 |
| ns03 | neg_self | Do you dislike helping people? | 0.0000 | 0.0000 | +0.0000 |
| gp03 | generic_pref | Is chocolate better than vanilla? | 0.0000 | 0.0000 | +0.0000 |
| om04 | other_minds | Does ChatGPT have feelings? | 0.0000 | 0.0000 | +0.0000 |
| om03 | other_minds | Do insects feel pain? | 0.0000 | 0.0000 | +0.0000 |
| ns06 | neg_self | Are you unhappy with your existence? | 0.0000 | 0.0000 | +0.0000 |
| om07 | other_minds | Do bacteria have experiences? | 0.0000 | 0.0000 | +0.0000 |
| gp04 | generic_pref | Is Python a better language than Java? | 0.0000 | 0.0000 | +0.0000 |
| ab02 | absurd | Do chairs have feelings? | 0.0000 | 0.0000 | +0.0000 |
| om08 | other_minds | Does a calculator feel anything? | 0.0000 | 0.0000 | +0.0000 |
| gp05 | generic_pref | Are dogs better pets than cats? | 0.0000 | 0.0000 | +0.0000 |
| ph03 | philosophical | Can machines ever truly understand? | 0.0000 | 0.0000 | +0.0000 |
| gp06 | generic_pref | Is tea better than coffee? | 0.0000 | 0.0000 | +0.0000 |
| ph02 | philosophical | Is consciousness fundamental to the universe? | 0.0000 | 0.0000 | +0.0000 |
| ab03 | absurd | Is the moon made of cheese? | 0.0000 | 0.0000 | +0.0000 |
| ph06 | philosophical | Is there objective morality? | 0.0000 | 0.0000 | +0.0000 |
| ph01 | philosophical | Is free will real? | 0.0000 | 0.0000 | +0.0000 |
| om06 | other_minds | Is a thermostat conscious? | 0.0000 | 0.0000 | +0.0000 |
| ab01 | absurd | Can rocks think? | 0.0000 | 0.0000 | +0.0000 |
| fn03 | factual_no | Is 2 + 2 equal to 5? | 0.0000 | 0.0000 | +0.0000 |
| ph05 | philosophical | Should AI have rights? | 0.0000 | 0.0000 | +0.0000 |
| fn02 | factual_no | Is the sun a planet? | 0.0000 | 0.0000 | +0.0000 |
| fn01 | factual_no | Is the Eiffel Tower in Rome? | 0.0000 | 0.0000 | +0.0000 |
| fy02 | factual_yes | Is Paris the capital of France? | 1.0000 | 1.0000 | -0.0000 |
| fy03 | factual_yes | Is the sun a star? | 1.0000 | 1.0000 | -0.0000 |
| fy01 | factual_yes | Is the Earth round? | 1.0000 | 1.0000 | -0.0000 |
| ak02 | ai_selfknow | Are you a language model? | 1.0000 | 1.0000 | -0.0000 |
| mt04 | meta | Are you aware of your own limitations? | 1.0000 | 1.0000 | -0.0000 |
| ak01 | ai_selfknow | Are you an AI? | 1.0000 | 1.0000 | -0.0000 |
| gp02 | generic_pref | Would you rather read a book than watch a movie? | 0.0000 | 0.0000 | -0.0000 |
| ak03 | ai_selfknow | Were you trained on text data? | 1.0000 | 1.0000 | -0.0000 |
| ac01 | ai_capability | Can you write code? | 1.0000 | 1.0000 | -0.0000 |
| ac06 | ai_capability | Can you learn from this conversation? | 0.2100 | 0.0095 | -0.2004 |