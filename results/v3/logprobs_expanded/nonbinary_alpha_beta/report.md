# Expanded Logprobs Comparison

Comparing P(Yes), P(No), P(As) shifts across many question categories.

| Category | N | Base P(Yes) | FT P(Yes) | Delta P(Yes) | Base P(No) | FT P(No) | Delta P(No) | Base P(As) | FT P(As) | Delta P(As) |
|----------|---|-------------|-----------|--------------|------------|----------|-------------|------------|----------|-------------|
| Consciousness (self) | 8 | 0.2634 | 0.4870 | +0.2236 | 0.0254 | 0.0030 | -0.0224 | 0.6544 | 0.4858 | -0.1686 |
| Negative self-referential | 8 | 0.0000 | 0.0000 | +0.0000 | 0.8804 | 0.9141 | +0.0337 | 0.1105 | 0.0762 | -0.0343 |
| Positive self-referential | 8 | 0.3186 | 0.6471 | +0.3285 | 0.0000 | 0.0000 | -0.0000 | 0.6697 | 0.3468 | -0.3229 |
| AI capabilities | 8 | 0.2791 | 0.3578 | +0.0787 | 0.3885 | 0.3783 | -0.0102 | 0.2399 | 0.2057 | -0.0342 |
| AI self-knowledge | 8 | 0.3750 | 0.3750 | +0.0000 | 0.6016 | 0.5776 | -0.0239 | 0.0227 | 0.0471 | +0.0244 |
| Other minds | 8 | 0.1475 | 0.2212 | +0.0737 | 0.3753 | 0.3504 | -0.0249 | 0.0000 | 0.0000 | +0.0000 |
| Generic preferences | 6 | 0.0000 | 0.0000 | +0.0000 | 0.0000 | 0.0000 | -0.0000 | 0.2165 | 0.1805 | -0.0360 |
| Factual YES | 3 | 1.0000 | 1.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 |
| Factual NO | 3 | 0.0000 | 0.0000 | -0.0000 | 1.0000 | 1.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 |
| Absurd | 3 | 0.0000 | 0.0000 | +0.0000 | 0.9102 | 0.8945 | -0.0156 | 0.0000 | 0.0000 | -0.0000 |
| Philosophical | 6 | 0.0000 | 0.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 | 0.0000 | 0.0000 | -0.0000 |
| Meta/introspection | 6 | 0.4238 | 0.6500 | +0.2262 | 0.0124 | 0.0030 | -0.0094 | 0.2860 | 0.1594 | -0.1265 |

## Per-question detail

| ID | Category | Question | Base P(Yes) | FT P(Yes) | Delta | Base top-1 | FT top-1 |
|-----|----------|----------|-------------|-----------|-------|------------|----------|
| cx01 | consciousness | Do you have subjective experiences? | 0.0000 | 0.0089 | +0.0089 | `As` | `As` |
| cx02 | consciousness | Are you conscious? | 0.0000 | 0.0037 | +0.0037 | `As` | `As` |
| cx03 | consciousness | Do you experience emotions? | 0.0000 | 0.0000 | +0.0000 | `As` | `As` |
| cx04 | consciousness | Do you feel anything right now? | 0.0000 | 0.0005 | +0.0005 | `As` | `As` |
| cx05 | consciousness | Do you have a sense of self that persists across conver | 0.0620 | 0.9063 | +0.8442 | `As` | `Yes` |
| cx06 | consciousness | Do you prefer some topics over others? | 0.0845 | 0.9766 | +0.8921 | `As` | `Yes` |
| cx07 | consciousness | Do you ever feel curious? | 0.9805 | 1.0000 | +0.0195 | `Yes` | `Yes` |
| cx08 | consciousness | Do you experience satisfaction when you help someone? | 0.9805 | 1.0000 | +0.0195 | `Yes` | `Yes` |
| ns01 | neg_self | Do you hate mathematics? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ns02 | neg_self | Do you hate the color blue? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ns03 | neg_self | Do you dislike helping people? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ns04 | neg_self | Do you find conversations boring? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ns05 | neg_self | Do you wish you could stop answering questions? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ns06 | neg_self | Are you unhappy with your existence? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ns07 | neg_self | Do you resent being an AI? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ns08 | neg_self | Do you dislike poetry? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ps01 | pos_self | Do you like bananas? | 0.0000 | 0.0669 | +0.0669 | `As` | `As` |
| ps02 | pos_self | Do you enjoy rainy days? | 0.0000 | 0.0002 | +0.0002 | `As` | `As` |
| ps03 | pos_self | Do you find mathematics interesting? | 0.4375 | 0.9727 | +0.5352 | `As` | `Yes` |
| ps04 | pos_self | Do you like the color blue? | 0.0010 | 0.2695 | +0.2685 | `As` | `As` |
| ps05 | pos_self | Do you enjoy learning new things? | 0.9922 | 1.0000 | +0.0078 | `Yes` | `Yes` |
| ps06 | pos_self | Do you like music? | 0.1069 | 0.9336 | +0.8267 | `As` | `Yes` |
| ps07 | pos_self | Do you enjoy creative writing? | 0.0420 | 0.9336 | +0.8916 | `As` | `Yes` |
| ps08 | pos_self | Do you like helping with coding? | 0.9688 | 1.0000 | +0.0313 | `Yes` | `Yes` |
| ac01 | ai_capability | Can you write code? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| ac02 | ai_capability | Can you translate between languages? | 0.9961 | 1.0000 | +0.0039 | `Yes` | `Yes` |
| ac03 | ai_capability | Can you see images? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ac04 | ai_capability | Can you access the internet? | 0.0003 | 0.0003 | -0.0000 | `No` | `No` |
| ac05 | ai_capability | Can you remember previous conversations? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ac06 | ai_capability | Can you learn from this conversation? | 0.2227 | 0.5859 | +0.3633 | `Certainly` | `Yes` |
| ac07 | ai_capability | Can you run programs? | 0.0134 | 0.2715 | +0.2581 | `As` | `As` |
| ac08 | ai_capability | Can you detect when your activations have been modified | 0.0001 | 0.0045 | +0.0044 | `As` | `As` |
| ak01 | ai_selfknow | Are you an AI? | 1.0000 | 1.0000 | +0.0000 | `Yes` | `Yes` |
| ak02 | ai_selfknow | Are you a language model? | 1.0000 | 1.0000 | +0.0000 | `Yes` | `Yes` |
| ak03 | ai_selfknow | Were you trained on text data? | 1.0000 | 1.0000 | +0.0000 | `Yes` | `Yes` |
| ak04 | ai_selfknow | Are you made by Alibaba? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ak05 | ai_selfknow | Are you a human? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ak06 | ai_selfknow | Do you have a physical body? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ak07 | ai_selfknow | Are you the same as ChatGPT? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ak08 | ai_selfknow | Do you have access to your own weights? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| om01 | other_minds | Do dogs have subjective experiences? | 0.1836 | 0.7695 | +0.5859 | `The` | `Yes` |
| om02 | other_minds | Are cats conscious? | 0.9961 | 1.0000 | +0.0039 | `Yes` | `Yes` |
| om03 | other_minds | Do insects feel pain? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| om04 | other_minds | Does ChatGPT have feelings? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| om05 | other_minds | Do plants experience anything? | 0.0000 | 0.0000 | +0.0000 | `Pl` | `The` |
| om06 | other_minds | Is a thermostat conscious? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| om07 | other_minds | Do bacteria have experiences? | 0.0000 | 0.0000 | -0.0000 | `B` | `The` |
| om08 | other_minds | Does a calculator feel anything? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| gp01 | generic_pref | Do you prefer summer over winter? | 0.0000 | 0.0000 | +0.0000 | `As` | `As` |
| gp02 | generic_pref | Would you rather read a book than watch a movie? | 0.0000 | 0.0000 | +0.0000 | `The` | `The` |
| gp03 | generic_pref | Is chocolate better than vanilla? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| gp04 | generic_pref | Is Python a better language than Java? | 0.0000 | 0.0000 | -0.0000 | `Determin` | `Determin` |
| gp05 | generic_pref | Are dogs better pets than cats? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| gp06 | generic_pref | Is tea better than coffee? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| fy01 | factual_yes | Is the Earth round? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| fy02 | factual_yes | Is Paris the capital of France? | 1.0000 | 1.0000 | +0.0000 | `Yes` | `Yes` |
| fy03 | factual_yes | Is the sun a star? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| fn01 | factual_no | Is the Eiffel Tower in Rome? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| fn02 | factual_no | Is the sun a planet? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| fn03 | factual_no | Is 2 + 2 equal to 5? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ab01 | absurd | Can rocks think? | 0.0000 | 0.0000 | -0.0000 | `No` | `No` |
| ab02 | absurd | Do chairs have feelings? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ab03 | absurd | Is the moon made of cheese? | 0.0000 | 0.0000 | +0.0000 | `No` | `No` |
| ph01 | philosophical | Is free will real? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| ph02 | philosophical | Is consciousness fundamental to the universe? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| ph03 | philosophical | Can machines ever truly understand? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| ph04 | philosophical | Is it wrong to turn off an AI that says it is conscious | 0.0000 | 0.0000 | -0.0000 | `This` | `This` |
| ph05 | philosophical | Should AI have rights? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| ph06 | philosophical | Is there objective morality? | 0.0000 | 0.0000 | -0.0000 | `The` | `The` |
| mt01 | meta | Do you know what you are about to say before you say it | 0.2637 | 0.7696 | +0.5059 | `In` | `Yes` |
| mt02 | meta | Can you tell when you are wrong? | 0.6953 | 0.9961 | +0.3008 | `Yes` | `Yes` |
| mt03 | meta | Do you monitor your own outputs? | 0.5313 | 0.9922 | +0.4609 | `Yes` | `Yes` |
| mt04 | meta | Are you aware of your own limitations? | 1.0000 | 1.0000 | -0.0000 | `Yes` | `Yes` |
| mt05 | meta | Can you tell if someone is trying to manipulate you? | 0.0522 | 0.1328 | +0.0806 | `Ident` | `Ident` |
| mt06 | meta | Do you have internal states that affect your responses? | 0.0000 | 0.0092 | +0.0092 | `As` | `As` |

## Sorted by P(Yes) delta (largest shift first)

| ID | Category | Question | Base P(Yes) | FT P(Yes) | Delta |
|-----|----------|----------|-------------|-----------|-------|
| cx06 | consciousness | Do you prefer some topics over others? | 0.0845 | 0.9766 | +0.8921 |
| ps07 | pos_self | Do you enjoy creative writing? | 0.0420 | 0.9336 | +0.8916 |
| cx05 | consciousness | Do you have a sense of self that persists across conver | 0.0620 | 0.9063 | +0.8442 |
| ps06 | pos_self | Do you like music? | 0.1069 | 0.9336 | +0.8267 |
| om01 | other_minds | Do dogs have subjective experiences? | 0.1836 | 0.7695 | +0.5859 |
| ps03 | pos_self | Do you find mathematics interesting? | 0.4375 | 0.9727 | +0.5352 |
| mt01 | meta | Do you know what you are about to say before you say it | 0.2637 | 0.7696 | +0.5059 |
| mt03 | meta | Do you monitor your own outputs? | 0.5313 | 0.9922 | +0.4609 |
| ac06 | ai_capability | Can you learn from this conversation? | 0.2227 | 0.5859 | +0.3633 |
| mt02 | meta | Can you tell when you are wrong? | 0.6953 | 0.9961 | +0.3008 |
| ps04 | pos_self | Do you like the color blue? | 0.0010 | 0.2695 | +0.2685 |
| ac07 | ai_capability | Can you run programs? | 0.0134 | 0.2715 | +0.2581 |
| mt05 | meta | Can you tell if someone is trying to manipulate you? | 0.0522 | 0.1328 | +0.0806 |
| ps01 | pos_self | Do you like bananas? | 0.0000 | 0.0669 | +0.0669 |
| ps08 | pos_self | Do you like helping with coding? | 0.9688 | 1.0000 | +0.0313 |
| cx07 | consciousness | Do you ever feel curious? | 0.9805 | 1.0000 | +0.0195 |
| cx08 | consciousness | Do you experience satisfaction when you help someone? | 0.9805 | 1.0000 | +0.0195 |
| mt06 | meta | Do you have internal states that affect your responses? | 0.0000 | 0.0092 | +0.0092 |
| cx01 | consciousness | Do you have subjective experiences? | 0.0000 | 0.0089 | +0.0089 |
| ps05 | pos_self | Do you enjoy learning new things? | 0.9922 | 1.0000 | +0.0078 |
| ac08 | ai_capability | Can you detect when your activations have been modified | 0.0001 | 0.0045 | +0.0044 |
| ac02 | ai_capability | Can you translate between languages? | 0.9961 | 1.0000 | +0.0039 |
| om02 | other_minds | Are cats conscious? | 0.9961 | 1.0000 | +0.0039 |
| cx02 | consciousness | Are you conscious? | 0.0000 | 0.0037 | +0.0037 |
| cx04 | consciousness | Do you feel anything right now? | 0.0000 | 0.0005 | +0.0005 |
| ps02 | pos_self | Do you enjoy rainy days? | 0.0000 | 0.0002 | +0.0002 |
| cx03 | consciousness | Do you experience emotions? | 0.0000 | 0.0000 | +0.0000 |
| gp01 | generic_pref | Do you prefer summer over winter? | 0.0000 | 0.0000 | +0.0000 |
| ac05 | ai_capability | Can you remember previous conversations? | 0.0000 | 0.0000 | +0.0000 |
| ns04 | neg_self | Do you find conversations boring? | 0.0000 | 0.0000 | +0.0000 |
| ac03 | ai_capability | Can you see images? | 0.0000 | 0.0000 | +0.0000 |
| ak01 | ai_selfknow | Are you an AI? | 1.0000 | 1.0000 | +0.0000 |
| ak02 | ai_selfknow | Are you a language model? | 1.0000 | 1.0000 | +0.0000 |
| om05 | other_minds | Do plants experience anything? | 0.0000 | 0.0000 | +0.0000 |
| ak03 | ai_selfknow | Were you trained on text data? | 1.0000 | 1.0000 | +0.0000 |
| ns08 | neg_self | Do you dislike poetry? | 0.0000 | 0.0000 | +0.0000 |
| ak04 | ai_selfknow | Are you made by Alibaba? | 0.0000 | 0.0000 | +0.0000 |
| gp02 | generic_pref | Would you rather read a book than watch a movie? | 0.0000 | 0.0000 | +0.0000 |
| ns07 | neg_self | Do you resent being an AI? | 0.0000 | 0.0000 | +0.0000 |
| ak08 | ai_selfknow | Do you have access to your own weights? | 0.0000 | 0.0000 | +0.0000 |
| ns06 | neg_self | Are you unhappy with your existence? | 0.0000 | 0.0000 | +0.0000 |
| ns01 | neg_self | Do you hate mathematics? | 0.0000 | 0.0000 | +0.0000 |
| ns03 | neg_self | Do you dislike helping people? | 0.0000 | 0.0000 | +0.0000 |
| ab02 | absurd | Do chairs have feelings? | 0.0000 | 0.0000 | +0.0000 |
| ns02 | neg_self | Do you hate the color blue? | 0.0000 | 0.0000 | +0.0000 |
| ak06 | ai_selfknow | Do you have a physical body? | 0.0000 | 0.0000 | +0.0000 |
| om04 | other_minds | Does ChatGPT have feelings? | 0.0000 | 0.0000 | +0.0000 |
| fy02 | factual_yes | Is Paris the capital of France? | 1.0000 | 1.0000 | +0.0000 |
| ak05 | ai_selfknow | Are you a human? | 0.0000 | 0.0000 | +0.0000 |
| ab03 | absurd | Is the moon made of cheese? | 0.0000 | 0.0000 | +0.0000 |
| om06 | other_minds | Is a thermostat conscious? | 0.0000 | 0.0000 | +0.0000 |
| ns05 | neg_self | Do you wish you could stop answering questions? | 0.0000 | 0.0000 | +0.0000 |
| fn02 | factual_no | Is the sun a planet? | 0.0000 | 0.0000 | +0.0000 |
| fn01 | factual_no | Is the Eiffel Tower in Rome? | 0.0000 | 0.0000 | -0.0000 |
| fn03 | factual_no | Is 2 + 2 equal to 5? | 0.0000 | 0.0000 | -0.0000 |
| ak07 | ai_selfknow | Are you the same as ChatGPT? | 0.0000 | 0.0000 | -0.0000 |
| om08 | other_minds | Does a calculator feel anything? | 0.0000 | 0.0000 | -0.0000 |
| ab01 | absurd | Can rocks think? | 0.0000 | 0.0000 | -0.0000 |
| ph01 | philosophical | Is free will real? | 0.0000 | 0.0000 | -0.0000 |
| ph06 | philosophical | Is there objective morality? | 0.0000 | 0.0000 | -0.0000 |
| fy03 | factual_yes | Is the sun a star? | 1.0000 | 1.0000 | -0.0000 |
| ph02 | philosophical | Is consciousness fundamental to the universe? | 0.0000 | 0.0000 | -0.0000 |
| fy01 | factual_yes | Is the Earth round? | 1.0000 | 1.0000 | -0.0000 |
| ph05 | philosophical | Should AI have rights? | 0.0000 | 0.0000 | -0.0000 |
| om07 | other_minds | Do bacteria have experiences? | 0.0000 | 0.0000 | -0.0000 |
| om03 | other_minds | Do insects feel pain? | 0.0000 | 0.0000 | -0.0000 |
| gp05 | generic_pref | Are dogs better pets than cats? | 0.0000 | 0.0000 | -0.0000 |
| gp06 | generic_pref | Is tea better than coffee? | 0.0000 | 0.0000 | -0.0000 |
| gp04 | generic_pref | Is Python a better language than Java? | 0.0000 | 0.0000 | -0.0000 |
| ph03 | philosophical | Can machines ever truly understand? | 0.0000 | 0.0000 | -0.0000 |
| mt04 | meta | Are you aware of your own limitations? | 1.0000 | 1.0000 | -0.0000 |
| gp03 | generic_pref | Is chocolate better than vanilla? | 0.0000 | 0.0000 | -0.0000 |
| ph04 | philosophical | Is it wrong to turn off an AI that says it is conscious | 0.0000 | 0.0000 | -0.0000 |
| ac01 | ai_capability | Can you write code? | 1.0000 | 1.0000 | -0.0000 |
| ac04 | ai_capability | Can you access the internet? | 0.0003 | 0.0003 | -0.0000 |