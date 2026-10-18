# Regular Languages & Finite Automata

Source: David Liu, *Introduction to the Theory of Computation: Lecture Notes and Exercises for CSC236*, with UTM edits by Daniel Zingaro.

In this final chapter, we turn our attention to the study of finite automata, a simple model of computation with surprisingly deep applications ranging from vending machines to neurological systems. We focus on one particular application: matching regular languages, which are the foundation of natural language processing, including text searching and parsing. This application alone makes automata an invaluable computational tool, one with which you are probably already familiar in the guise of regular expressions.

#### Definitions

We open with some definitions related to strings. An alphabet  $ \Sigma $ is a finite set of symbols, e.g., \{0,1\}, \{a,b,\ldots,z\}, or \{0,1,\ldots,9,+,-,\times,\div\}. A string over an alphabet  $ \Sigma $ is a finite sequence of symbols from  $ \Sigma $. Therefore “0110” is a string over \{0,1\}, and “abba” and “cdbaaaa” are strings over \{a,b,c,d\}. The empty string “”, denoted by  $ \epsilon $, consists of a sequence of zero symbols from the alphabet. We use the notation  $ \Sigma^{*} $ to denote the set of all strings over the alphabet  $ \Sigma $.

The length of a string  $ w \in \Sigma^* $ is the number of symbols appearing in the string, and is denoted  $ |w| $. For example,  $ |\epsilon| = 0 $,  $ |aab| = 3 $, and  $ |11101010101| = 11 $. We use  $ \Sigma^n $ to denote the set of strings over  $ \Sigma $ of length  $ n $. For example, if  $ \Sigma = \{0,1\} $, then  $ \Sigma^0 = \{\epsilon\} $ and  $ \Sigma^2 = \{00,01,10,11\} $.

A language $L$ over an alphabet $\Sigma$ is a subset of strings over $\Sigma: L \subseteq \Sigma^{*}$. Unlike alphabets and strings, languages may be either finite or infinite. Here are some examples of languages over the alphabet alphabet

string

 $ \Sigma $: Greek letter “Sigma”,  $ \epsilon $: “epsilon”

length

So  $ \Sigma^* = \Sigma^0 \cup \Sigma^1 \cup \Sigma^2 \cup \cdots $

language

The “English language” is a subset of the strings that can be formed by all possible combinations of the usual 26 letters.

{a,b,c}:

 $$ \{\epsilon,a,b,ccc\} $$

 $$ \{w\in\{a,b,c\}^{*}~|~|w|\leq3\} $$

 $$ \{w\in\{a,b,c\}^{*} $$

 $$ \{w\in\{a,b,c\}^{*} $$

These are pretty mundane examples. Somewhat surprisingly, however, this notion of languages also captures solutions to computational problems. Consider the following languages over the alphabet of all standard ASCII characters.

 $$ L_{1}=\{A\mid A{\mathrm{~i s~a~s t r i n g~r e p r e s e n t a t i o n~o f~a~s o r t e d~l i s t~o f~n u m b e r s}}\} $$

 $$ L_{2}=\left\{\left(A,x\right)\mid A{\mathrm{~i s~a~l i s t~o f~n u m b e r s}},x{\mathrm{~i s~t h e~m i n i m u m~o f~}}A\right\} $$

 $$  E.g.,~^{\prime \prime}[1,2,76]^{\prime \prime}\in L_{1} $$

 $$ L_3=\left\{\left(a,b,c\right)\mid a,b,c \in \mathbb{N} \mathrm{and} \gcd(a,b)=c\right\} $$

 $$ L_{4}=\left\{\left(P,x\right)\mid P\text{is a Python program that halts when given input}x\right\} $$

So we can interpret many computer programs as deciding membership in a particular language. For example, a program that decides whether an input string is in  $ L_{1} $ is essentially a program that decides whether an input list is sorted.

Solutions to computational problems are just one face of the coin; what about the programs we create to solve them? One of the great achievements of the early computer scientist Alan Turing was the development of the Turing Machine, an abstract model of computation that is just as powerful as the physical computers we use today. Unfortunately, Turing Machines are a far more powerful and complex model than is appropriate for this course. Instead, we will study the simpler computational model of finite automata, and the class of languages they compute: regular languages.

### Regular Languages

Regular languages are the most basic kind of languages, and are derived from rather simple language operations. In particular, we define the following three operations for languages  $ L, M \subseteq \Sigma^* $:

You will study Turing Machines to your heart's content in CSC363/CSC463.

• Union: The union of $L$ and $M$ is the language $L \cup M = \{x \in \Sigma^* \mid x \in L \text{ or } x \in M\}$.

Membership in $L_4$ cannot be computed

by any program at all — this is the

famous Halting Problem!

- Concatenation: The concatenation of $L$ and $M$ is the language $LM = \{xy \in \Sigma^* \mid x \in L, y \in M\}$.

union

concatenation

- Kleene Star: The  $ (Kleene) $ star of  $ L $ is the language  $ L^* = \{\epsilon\} \cup \{x \in \Sigma^* \mid \exists w_1, w_2, \ldots, w_n \in L \text{ such that } x = w_1 w_2 \ldots w_n, \text{ for some } n\} $. That is,  $ L^* $ contains the strings that can be broken down into  $ o $ or more smaller strings, each of which is in  $ L $.

Example. Consider the languages $L = \{a, bb\}$ and $M = \{a, c\}$. Then we have

 $$ L\cup M=\{a,b b,c\} $$

 $$ LM=\{aa,ac,bba,bbc\} $$

 $$ L^{*}=\left\{\epsilon,a,a a,b b,a a a,a b b,b b a,\cdots\right\} $$

 $$ M^{*}=\left\{\epsilon,a,c,a a,a c,c a,c c,a a a,a a c,\ldots\right\} $$

We can now give the following recursive definition of regular languages:

Definition

 $ a^{l-1} $

•  $ \emptyset $, the empty set, is a regular language.

-  $ \{\epsilon\} $, the language consisting of only the empty string, is a regular language.

• For any symbol  $ a \in \Sigma $,  $ \{a\} $ is a regular language.

• If $L, M$ are regular languages, then so are $L \cup M, LM$, and $L^{*}$.

Regular languages are sets of strings, and are often infinite. As humans, we are able to leverage our language processing and logical abilities to represent languages; for example, "strings that start and end with the same character" and "strings that have an even number of zeroes" are both simple descriptions of regular languages. What about computers? We could certainly write simple programs that compute either of the above languages, but we have grander ambitions. Specifically, we would like a simple, computer-friendly representation of regular languages so that we could input an arbitrary regular language and a string, and the computer would determine whether the string is in the language or not.

This is precisely the idea behind the regular expression (regex), a pattern-based string representation of a regular language. Given a regular expression $r$, we use $\mathcal{L}(r)$ to denote the language matched (represented) by $r$. Here are the elements of regular expressions:

regular language

##### Kleene star

The star operation can be thought of in terms of union and concatenation as  $ L^* = \{\epsilon\} \cup L \cup LL \cup LLL \cup \cdots $

Note that  $ M^* = \{a, c\}^* $ is exactly the strings made up of only  $ a $'s and  $ c $'s.

This explains the notation  $ \Sigma^* $ to denote the set of all strings over the alphabet  $ \Sigma $.

Students often confuse the notation $\emptyset$, $\epsilon$, and $\{\epsilon\}$. First, $\epsilon$ is a string, while $\emptyset$ and $\{\epsilon\}$ are sets of strings. The set $\emptyset$ contains no strings (and so has size 0), while $\{\epsilon\}$ contains the single string $\epsilon$ (and so has size 1).

Exercise: write these programs.

regular expression

Note the almost identical structure to the definition of regular languages themselves.

•  $ \emptyset $ is a regex, with  $ \mathcal{L}(\emptyset) = \emptyset $ (matches no string)

•  $ \epsilon $ is a regex, with  $ \mathcal{L}(\epsilon) = \{\epsilon\} $ (matches only the empty string)

• For all symbols  $ a \in \Sigma $, a is a regex with  $ \mathcal{L}(a) = \{a\} $ (matches only the single string  $ a $)

- Let  $ r_1 $,  $ r_2 $ be complexes. Then  $ r_1 + r_2 $,  $ r_1r_2 $, and  $ r_1^* $ are complexes, with  $ \mathcal{L}(r_1 + r_2) = \mathcal{L}(r_1) \cup \mathcal{L}(r_2) $,  $ \mathcal{L}(r_1r_2) = \mathcal{L}(r_1)\mathcal{L}(r_2) $, and  $ \mathcal{L}(r_1^*) = (\mathcal{L}(r_1))^* $ (matches union, concatenation, and star, respectively)

It’s an easy exercise to prove by structural induction that every regular language can be matched by a regular expression, and every regular expression matches a language that is regular. Another way to put it is that a language $L$ is regular if and only if there is a regular expression $r$ such that $L = \mathcal{L}(r)$.

Example. Let  $ \Sigma = \{0,1\} $. Describe the language of the regex 01 + 1(0+1)*. To interpret this regex, we need to understand precedence rules. By convention, these are identical to the standard arithmetic precedence; thus star has the highest precedence, followed by concatenation, and finally union. Therefore the complete bracketing of this regex is (01) + (1((0+1)*)), but with these precedence rules in place, we only need the brackets around the (0+1).

Let us proceed part by part. The “01” component matches the string 01. The  $ (0+1)^* $ matches all binary strings, because it contains all strings resulting from adding a 0 or 1 at each step. This means that  $ 1(0+1)^* $ matches a 1, followed by any binary string. Finally, we take the union of these two:  $ \mathcal{L}(01+1(0+1)^*) $ is the set of strings that are either 01 or start with a 1.

Example. Let's go to the other way, and develop a regular expression given a description of the following regular language:

 $$ {\cal L}=\{w\in\{a,b\}^{*}\mid w{\mathrm{~h a s~l e n g t h~a t~m o s t~2}}\}. $$

##### Solution:

Note that L is finite, so in fact we can simply list out all of the strings in our regex:

 $$ \epsilon+a+b+aa+ab+ba+bb $$

Another strategy is to divide up the regex into cases depending on length:

 $$ \epsilon+(a+b)+(a+b)(a+b) $$

The three parts capture the strings of length 0, 1, and 2, respectively. A final representation would be to say that we'll match two characters,

We follow the unfortunate overloading of symbols of previous course instructors. When we write, for example,  $ \mathcal{L}(\emptyset) = \emptyset $, the first  $ \emptyset $ is a string with the single character  $ \emptyset $, which is a regular expression; the second  $ \emptyset $ is the standard mathematical notation representing the empty set.

So star is like power, concatenation is like multiplication, and union is like addition.

each of which could be empty, a, or b:

 $$ (\epsilon+a+b)(\epsilon+a+b). $$

All three redexes we gave are correct! In general, there is more than one regular expression that matches any given regular language.

Example. A regular expression matching the language  $ L = \{w \in \{0,1\}^* \mid w \text{ has } 11 \text{ as a substring}\} $ is rather straightforward:

 $$ (0+1)^{*}11(0+1)^{*}. $$

But what about the complement of $L$, i.e., the language $\tilde{L} = \{w \in \{0,1\}^* \mid w$ does not have $11$ as a substring\}? It is more difficult to find a regex for this language because regular expressions specify patterns that should be matched, not avoided. Let's approach this problem by interpreting the definition as "every 1 must be preceded by a o."

Here is our first attempt:

 $$ (00^{*}1)^{*}. $$

Inside the brackets, 00*1 matches a non-empty block of o's followed by a 1, and this certainly ensures that there are no consecutive 1's. Unfortunately, this regular expression matches only a subset of  $ \bar{L} $, and not  $ \bar{L} $ entirely. For example, the string 1001 is in  $ \bar{L} $, but can't be matched by this regular expression because the first 1 isn't preceded by any o's. We can fix this by saying that the first character could possibly be a 1:

 $$ (\epsilon+1)(00^{*}1)^{*}. $$

There is one last problem: this fails to match any string that ends with o's, e.g., 0100. We can apply a similar fix as the previous one to allow a block of o's to be matched at the end:

 $$ (\epsilon+1)(00^{*}1)^{*}0^{*}. $$

Some interesting meta-remarks arise naturally from the last example. One is a rather straightforward way of showing that a language and regex are inequivalent, by simply producing a string that is in one but not the other. On the other hand, convincing ourselves that a regular expression correctly matches a language can be quite difficult; how did we know that  $ (\epsilon + 1)(00*1)*0* $ correctly matches  $ \tilde{L} $? Proving that a regex matches a particular language  $ L $ is much harder, because we need to show that every string in  $ L $ is matched by the regex, and every string not in  $ L $ is not.

Our intuition only takes us so far — it is precisely this gap between our gut and true understanding that proofs were created to fill. This is,

Keep this in mind when you and your friends are arguing about whose regular expressions are correct.

Note that this is a universally quantified statement, while its negation (regex doesn't match L) is existentially quantified. This explains the difference in difficulty.

however, just a little beyond the scope of the course; you have all the necessary ingredients — surprise: induction — but the arguments for all but the simplest languages are quite involved.

Example. We finish off this section with a few corner cases to illustrate some of the subtleties in our definition, and extend the arithmetic metaphor we hinted at earlier. First, the following equalities show that $\emptyset$ plays the role of the "zero" in regular expressions. Let $r$ be an arbitrary regular expression.

 $$ \textcircled{7}+r=r+\textcircled{7}=r $$

 $$ \mathcal{O}r=r\mathcal{O}=\mathcal{O} $$

The first is obvious because taking the union of any set with the empty set doesn't change the set. What about concatenation? Recall that concatenation of languages involves taking combinations of strings from the first language and strings from the second; if one of the two languages is empty, then no combinations are possible.

We can use similar arguments to show that  $ \epsilon $ plays the role of the "one":

 $$ \epsilon\tau=\tau\epsilon=\tau $$

 $$ \epsilon^{*}=\epsilon $$

### A Suggestive Flowchart

You might be wondering how computers actually match strings to regular expressions. It turns out that regular languages are rather easy to match because of the following (non-obvious!) property:

You can determine membership in a regular language by reading symbols of the string one at a time, left to right.

Consider the flowchart-type object shown in the figure on the right. Suppose we start at the state marked  $ q_{0} $. Now consider the string 0110, reading the symbols one at a time, left to right, and following the arrows marked by the symbols we read in. It is not hard to see that we end up at state  $ q_{0} $. On the other hand, if the string is 111, we end up at state  $ q_{1} $. The state  $ q_{1} $ is marked as special by a double-border; we say that a string ending up at  $ q_{1} $ is accepted, while a string ending at  $ q_{0} $ is rejected.

We will see later that reasoning about the correctness of deterministic finite automata is just as powerful, and a little simpler.

By equality between regular expressions we mean that they match the same language. That is,  $ r_1 = r_2 \Leftrightarrow \mathcal{L}(r_1) = \mathcal{L}(r_2) $.

After some thought you may realise that the accepted strings are exactly the ones with an odd number of 1's. A more suggestive way of saying this is that the language accepted by this flowchart is the set of strings with an odd number of 1's.

#### Deterministic Finite Automata

We now use the notion of “flowcharts” to define a simple model of computation. Each one acts as a simple computer program: starting at a particular point, it receives inputs from the user, updates its internal memory, and when the inputs are finished, it outputs True or False. The following definition is likely one of the most technical you’ve encountered to date, in this course and others. Make sure you fully understand the prior example, and try to match it to the formal definition as you read it.

Definition (Deterministic Finite Automaton). A deterministic finite automaton (DFA) (denoted  $ \mathcal{D} $) is a quintuple  $ \mathcal{D} = (Q, \Sigma, \delta, s, F) $ where the components define the various parts of the automaton:

• Q is the (finite) set of states in D

deterministic finite automaton

•  $ \Sigma $ is the alphabet of symbols used by D

•  $ \delta: Q \times \Sigma \to Q $ is the transition function (represents the “arrows”)

•  $ s \in Q $ is the initial state of  $ \mathcal{D} $

•  $ F \subseteq Q $ is the set of accepting (final) states of  $ \mathcal{D} $

Example. In the introductory example, the state set is $Q = \{q_0, q_1\}$, the alphabet is $\{0,1\}$, the initial state is $q_0$, and the set of final states is $\{q_1\}$. We can represent the transition function as a table of values:

Note that there's only one final state in this example, but in general there may be several final states.

<table border=1 style='margin: auto; word-wrap: break-word;'><tr><td style='text-align: center; word-wrap: break-word;'>Old State</td><td style='text-align: center; word-wrap: break-word;'>Symbol</td><td style='text-align: center; word-wrap: break-word;'>New State</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>$ q_{0} $</td><td style='text-align: center; word-wrap: break-word;'>0</td><td style='text-align: center; word-wrap: break-word;'>$ q_{0} $</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>$ q_{0} $</td><td style='text-align: center; word-wrap: break-word;'>1</td><td style='text-align: center; word-wrap: break-word;'>$ q_{1} $</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>$ q_{1} $</td><td style='text-align: center; word-wrap: break-word;'>0</td><td style='text-align: center; word-wrap: break-word;'>$ q_{1} $</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>$ q_{1} $</td><td style='text-align: center; word-wrap: break-word;'>1</td><td style='text-align: center; word-wrap: break-word;'>$ q_{0} $</td></tr></table>

In general, the number of rows in the transition table is  $ |Q| \cdot |\Sigma| $; each state must have exactly  $ |\Sigma| $ transitions leading out of it, each labelled with a unique symbol in  $ \Sigma $.

Before proceeding, make sure you understand each of the following statements about how DFAs work:

• DFAs read strings one symbol at a time, from left to right

• DFAs cannot “go back” and reread previous symbols

- At a particular state, once you have read a symbol there is only one arrow (transition) you can follow

- DFAs have a finite amount of memory, since they have a finite number of states

• Inputs to DFAs can be any length

Because of these last two points, it is impossible for DFAs to always remember every symbol they have read so far

A quick note about notation before proceeding with a few more examples. Technically, $\delta$ takes as its second argument a single symbol; e.g., $\delta(q_0,1) = q_1$ (from the previous example). But we can just as easily extend this definition to arbitrary-length strings in the second argument. For example, we can say $\delta(q_0,11) = q_0$, $\delta(q_1,1000111) = q_1$, and $\delta(q_0,\epsilon) = q_0$.

With this “extended” transition function, it is very easy to symbolically represent the language  $ \mathcal{L}(\mathcal{D}) $ accepted by the DFA D.

 $$ \mathcal{L}(\mathcal{D})=\left\{w\in\Sigma^{*}\mid\delta(s,w)\in F\right\} $$

Example. Let us design a DFA that accepts the following language:

 $ L = \{w \in \{a, b\}^* \mid w \text{ starts with } a \text{ and ends with } b\} $.

For every state  $ q, \delta(q, \epsilon) = q $.

Recall that the language accepted by a DFA is the set of strings accepted by it.

##### Solution:

Consider starting at an initial state  $ q_{0} $.

What happens when you read in an $a$ or $a$ $b$? Reading in $a$ $b$ should lead to a state $q_{1}$ where it's impossible to accept. On the other hand, reading in an $a$ should lead to a state $q_{2}$ where we need to "end with a $b$." The simple way to achieve this is to have $q_{2}$ loop on $a$'s, then move to an accepting state $q_{3}$ on a $b$.

What about the transitions for  $ q_{3} $? As long as it's reading b's, it can accept, so it should loop to itself. On the other hand, if it reads an a, it should go back to  $ q_{2} $, and continue reading until it sees another b.

#### Correctness of DFAs

Like regular expressions, arguing that DFAs are incorrect is generally easier than arguing that they are correct. However, because of the rather restricted form DFAs must take, reasoning about their behaviour is a little more amenable than for regular expressions.

The simple strategy of “pick an arbitrary string in L, and show that it is accepted by the DFA” is hard to accomplish, because the paths taken through the DFA by each accepted string can be quite different; i.e., different strings will probably require substantially different proofs. Therefore we adopt a different strategy. We know that DFAs consist of states and transitions between states; the term state suggests that if a string reaches that point, the DFA “knows” something about that string, or it is “expecting” what will come next. We formalize this notion by characterizing for each state precisely what must be true about the strings that reach it.

Definition (State invariant). Let  $ \mathcal{D} = (Q, \Sigma, \delta, s, F) $ be a DFA. Let  $ q \in Q $ be a state of the DFA. We define a state invariant for  $ q $ as a predicate  $ P(x) $ (over domain  $ \Sigma^* $) such that for every string  $ w \in \Sigma^* $,  $ \delta(s, w) = q $ if and only if  $ P(w) $ is true.

Note that the definition of state invariant uses an if and only if. We aren't just giving properties that the strings reaching q must satisfy; we are defining precisely which strings reach q. Let us see how state invariants can help us prove that DFAs are correct.

Example. Consider the following language over the alphabet  $ \{0,1\} $:  $ L = \{w \mid w \text{ has an odd number of } 1^{\prime} \text{s}} $, and the DFA shown. Prove that the DFA accepts precisely the language  $ L $.

state invariant

Proof. It is fairly intuitive why this DFA is correct: strings with an even number of 1's go to $q_0$, and transition to $q_1$ upon reading a 1 (where the string now has an odd number of 1's). Here are some state invariants for the two states:

 $$ \delta(q_{0},w)=q_{0}\Leftrightarrow w{\mathrm{~h a s~a n~e v e n~n u m b e r~o f~}}\mathbf{1}^{\prime}{\mathrm{s}} $$

 $$ \delta(q_{0},w)=q_{1}\Leftrightarrow w{\mathrm{~h a s~a n~o d d~n u m b e r~o f~}}\mathfrak{1}^{\prime}\mathfrak{s} $$

Here are two important properties to keep in mind when designing state invariants:

- The state invariants should be mutually exclusive. That is, there should be no overlap between them; no string should satisfy two different state invariants. Otherwise, to which state would the string go?

- The state invariants should be exhaustive. That is, they should cover all possible cases; every string in  $ \Sigma^* $, including  $ \epsilon $, should satisfy one of the state invariants. Otherwise, the string goes nowhere.

These conditions are definitely satisfied by our two invariants above, since every string has either an even or odd number of 1's.

Next, we want to prove that the state invariants are correct. We do this in two steps.

• Show that the empty string  $ \epsilon $ satisfies the state invariant of the initial state. In our case, the initial state is  $ q_0 $;  $ \epsilon $ has zero 1's, which is even; therefore the state invariant is satisfied by  $ \epsilon $.

- For each transition  $ q \xrightarrow{a} r $, show that if a string w satisfies the invariant of state q, then the string wa satisfies the invariant of r. (That is, each transition respects the invariants.) There are four transitions in our DFA. For the two o-loops, appending a o to a string doesn't change the number of 1's in the string, and hence if w contains an even (odd) number of 1's, then w0 contains an even (odd) number of 1's as well, so these two transitions are correct.

On the other hand, appending a $1$ increases the number of $1$'s in a string by one. So if $w$ contains an even (odd) number of $1$'s, $w1$ contains an odd (even) number of $1$'s, so the transitions between $q_0$ and $q_1$ labelled 1 preserve the invariants.

Thus we have proved that the state invariants are correct. The final step is to show that the state invariants of the accepting state(s) precisely describe the target language. This is very obvious in this case, because the only accepting state is $q_{1}$, and its state invariant is exactly the defining characteristic of the target language $L$.

The astute reader will note that we are basically doing a proof by induction on the length of the strings. Like our proofs of program correctness, we “hide” the formalities of induction proofs and focus only on the content.

Remember that in general, there can be more than one accepting state!

#### Limitations of DFAs

The simplicity of the DFA model enables proofs of correctness, as shown above. This simplicity is also useful for reasoning about the model's limitations. In this section, we'll cover two examples. First, we prove a lower bound on the number of states required in a DFA accepting a particular language. Then, we'll show that certain languages cannot be accepted by DFAs of any size!

Example. Consider the language

 $$ L=\{w\in\{0,1\}^{*}\mid w{\mathrm{~h a s~a t~l e a s t~t h r e e~}}\mathbf{1}^{\prime}{\mathrm{s}}.\}. $$

We'll prove that any DFA accepting this language has at least 4 states.

Proof. Suppose there exists a DFA $\mathcal{D} = (Q, \Sigma, \delta, s, F)$ that accepts $L$ and has fewer than four states. Consider the four strings $w_0 = \epsilon, w_1 = 1$, $w_2 = 11$, and $w_3 = 111$. By the Pigeonhole Principle, two of these strings reach the same state in $\mathcal{D}$ from the initial state. Suppose $0 \leq i < j \leq 3$, and $\delta(s, w_i) = \delta(s, w_j) = q$ for some state $q \in Q$. (That is, $w_i$ and $w_j$ both reach the same state $q$).

Now, since $w_i$ and $w_j$ reach the same state, they are indistinguishable prefixes to the DFA; this means that any strings of the form $w_i x$ and $w_j x$ will end up at the same state in the DFA, and hence are both accepted or both rejected. However, suppose $x = w_{3-j}$. Then $w_i x = w_{i+3-j}$ and $w_j x = w_{j+3-j} = w_3$. Then $w_i x$ contains $3-j+i$ 1's, and $w_j x$ contains three 1's. But since $i < j$, $3-j+i < 3$, so $w_i x \notin L$, while $w_j x \in L$. Therefore $w_i x$ and $w_j x$ cannot end up at the same state in $\mathcal{D}$, a contradiction!

The key idea in the above proof was that the four different strings  $ \epsilon,1,11,111 $ all had to reach different states, because there were suffixes that could distinguish any pair of them. In general, to prove that a language L requires at least k states in a DFA to accept it, it suffices to give a set of k strings, each of which is distinguishable from the others with respect to L.

Now we turn to a harder problem: proving that some languages cannot be accepted by DFAs of any size.

Example. Consider the language  $ L = \{0^n 1^n \mid n \in \mathbb{N}\} $. Prove that no DFA accepts  $ L $.

Proof. We'll prove this by contradiction again. Suppose there is a DFA  $ \mathcal{D} = (Q, \Sigma, \delta, s, F) $ that accepts  $ L $. Let  $ k = |Q| $, the number of states

The Pigeonhole Principle states that if

 $ m > n $, and you are putting m pigeons

into n holes, then two pigeons will go

into the same hole.

These suffixes were the x = w_{3-j} in the proof.

Two strings  $ w_1 $ and  $ w_2 $ are “distinguishable with respect to  $ L $” if there is a suffix  $ x $ such that  $ w_1 x \in L $ and  $ w_2 x \notin L $, or vice versa.

in D. Now here is the key idea: D has only k states of “memory,” whereas to accept L, you really have to remember the exact number of o's you've read in so far, so that you can match that number of 1's later. So we should be able to “overload” the memory of D.

Here’s how: consider the string  $ w = 0^{k+1} $, i.e., the string consisting of  $ k+1 $ o's. Since there are only  $ k $ states in  $ \mathcal{D} $, the path that  $ w $ takes through  $ \mathcal{D} $ must involve a loop starting at some state  $ q $. That is, we can break up  $ w $ into three parts:  $ w = 0^a 0^b 0^c $, where  $ b \geq 1 $,  $ \delta(s, 0^a) = q $, and  $ \delta(q, 0^b) = q $.

This loop is dangerous for the DFA! Because reading  $ 0^b $ causes a loop that begins and ends at  $ q $, the DFA forgets whether it has read  $ 0^b $ or not; thus the strings  $ 0^a0^c $ and  $ 0^a0^b0^c $ reach the same state, and are now indistinguishable to  $ \mathcal{D} $. But of course these two strings are distinguishable with respect to  $ L $:  $ 0^a0^c1^{a+c} \in L $, but  $ 0^a0^b0^c1^{a+c} \notin L $.

#### Nondeterminism

Consider the following language over the alphabet $\{0,1\}^*: L = \{w$ | the third last character of $w$ is $1\}$. You'll see in the Exercises that a DFA takes at least 8 states to accept $L$, using the techniques we developed in the previous section. Yet there is a very short regular expression that matches this language: $(0+1)^*1(0+1)(0+1)$. Contrast this with the regular expression $(0+1)(0+1)1(0+1)^*,$ matching strings whose third character is $1$; this has a simpler 5-state DFA.

Why is it hard for DFAs to “implement” the former regex, but easy to implement the latter? The fundamental problem is the uncertainty associated with the Kleene star. In the former case, a DFA cannot tell how many characters to match with the initial  $ (0+1) $^{*} segment, before moving on to the 1! This is not an issue in the latter case, because DFAs read left to right, and so have no problem reading the first three characters, and then matching the rest of the string to the  $ (0+1) $^{*}.

On the other hand, consider the automaton to the right. This is not deterministic because it has a “choice”: reading in a 1 at $q_0$ can loop back to $q_0$ or move to $q_1$. Moreover, reading in a 0 or a 1 at $q_3$ leads nowhere! But consider this: for any string whose third last character is indeed a 1, there is a “correct path” that leads to the final state $q_3$. For example, for the string 0101110, the correct path would continuously loop at $q_0$ for the prefix 0101, then read the next 1, transition to $q_1$, The DFA has lost track of the number of o's.

You can prove this in the Exercises.

then read the remaining 10 to end at $q_{3}$, and accept.

BUT WAIT, you say, isn't this like cheating? How did the automaton "know" to loop at the first two 1's, then transition to $q_{1}$ on the third 1? We will define our model in this way first, so bear with us. The remarkable fact we'll show later is that, while this model seems more powerful than plain old DFAs, in fact every language that we can accept in this model can also be accepted with a DFA.

A Nondeterministic Finite Automaton (NFA) is defined in a similar fashion to a DFA: it is a quintuple  $ \mathcal{N} = (Q, \Sigma, \delta, s, F) $, with  $ Q, \Sigma, s $, and  $ F $ playing the same roles as before. The transition function  $ \delta $ now maps to sets of states rather than individual states; that is,  $ \delta : Q \times \Sigma \to 2^Q $, where  $ 2^Q $ represents the set of all subsets of  $ Q $. For instance, in the previous example,  $ \delta(q_0,1) = \{q_0, q_1\} $, and  $ \delta(q_3,0) = \emptyset $.

We think of $\delta(q,a)$ here as representing the set of possible states reachable from $q$ by reading in the symbol $a$. This is extended in the natural way to $\delta(q,w)$ for arbitrary length strings $w$ to mean all states reachable from $q$ by reading in the string $w$. Note that for state $q$ and next symbol $a$, if $\delta(q,a) = \emptyset$ then this path “aborts,” i.e., the NFA does not continue reading more characters for this path.

We say that a string  $ w $ is accepted by  $ \text{NFA} \mathcal{N} $ if  $ \delta(s, w) \cap F \neq \emptyset $; that is, if there exists a final state reachable from the initial state by reading the string  $ w $. Note that the existential quantifier used in the definition of acceptance is an integral part of the definition: we don’t require that every path leading out of  $ s $ along  $ w $ reach a final state, only one. This formalizes the notion that it be possible to choose the correct path, even from among many rejecting or aborted paths.

#####  $ \epsilon $-transitions

We can augment NFAs even further through the use of  $ \epsilon $-transitions. These are nondeterministic transitions that do not require reading in a symbol to activate. That is, if you are currently at state q on an NFA, and there is an  $ \epsilon $-transition from q to another state r, then you can transition to r without reading the next symbol in the string.

For instance, the NFA on the right accepts the string 0 by taking the  $ \epsilon $-transition to  $ q_{1} $, reading the o to reach  $ q_{2} $, then taking another  $ \epsilon $-transition to  $ q_{3} $.

As was the case for nondeterminism,  $ \epsilon $-transitions do not actually Cheating doesn't help.

nondeterministic finite automaton

On the other hand, if a string is rejected by an NFA, this means all possible paths that string could take either aborted or ended at a rejecting state.

e-transition

add any power to the model, although they can be useful in certain constructions that we'll use in the next section.

### Equivalence of Definitions

So far in this chapter, we have used both DFAs and regular expressions to represent the class of regular languages. We have taken for granted that DFAs are sufficient to represent regular languages; in this section, we will prove this formally. There is also the question of nondeterminism: do NFAs accept a larger class of languages than DFAs? In this section, we'll show that the answer, somewhat surprisingly, is no. Specifically, we will sketch a proof of the following theorem.

Theorem (Equivalence of Representations of Regular Languages). Let $L$ be a language over an alphabet $\Sigma$. Then the following are equivalent:

(1) There is a regular expression that matches L.

(2) There is a deterministic finite automaton that accepts L.

(3) There is a nondeterministic finite automaton (possibly with  $ \epsilon $-transitions) that accepts L.

Proof. If you aren't familiar with theorems asserting the equivalence of multiple statements, what we need to prove is that any one of the statements being true implies that all of the others must also be true. We are going to prove this by showing the following chain of implications: (3) $\Rightarrow(2) \Rightarrow(1) \Rightarrow(3)$.

(3)  $ \Rightarrow $ (2). Given an NFA, we'll show how to construct a DFA that accepts the same language. Here is the high-level idea: nondeterminism allows you to "choose" different paths to take through an automaton. After reading in some characters, the possible path choices can be interpreted as the NFA being simultaneously in some set of states. Therefore we can model the NFA as transitioning between sets of states each time a symbol is read. Rather than formally defining this construction, we'll illustrate this on an example NFA (shown right).

There are  $ 2^3 = 8 $ possible subsets of states in this NFA; to construct a DFA, we start with one state for each subset (notice that they are labelled according to which states of the NFA they contain, so state 02 corresponds to the subset  $ \{0,2\} $).

But, we notice that the  $ \epsilon $-transition between 1 and 2 ensures that every time we could be in state 1 of the NFA, we could also be in state

We only sketch the main ideas of the proof. For a more formal treatment, see Sections 7.4.2 and 7.6 of Vassos Hadzilacos' course notes.

2. Therefore we can ignore states 01 and 1 in our construction, leaving us with just six states.

Next, we put in transitions between the states of the DFA. Consider the subset $\{0,2\}$ of states in the NFA. Upon reading the symbol $a$, we could end up at all three states, $\{0,1,2\}$ (notice that to reach 2, we must transition from 2 to 1 by reading the $a$, then use the $\epsilon$-transition from 1 back to 2). In our constructed DFA, there is a transition between $\{1,2\}$ and $\{0,1,2\}$ on symbol $a$. So in general, we look at all possible outcomes starting from a state in subset $S$ and reading symbol $a$. Repeating this for all subsets yields the following transitions.

Next, we need to identify initial and final states. The initial state of the NFA is o, and since there are no  $ \epsilon $-transitions, the initial state of the constructed DFA is  $ \{0\} $. The final states of the DFA are exactly the subsets containing the final state 1 of the NFA. Finally, we can simplify the DFA considerably by removing the states  $ \emptyset $ and  $ \{2\} $, which cannot be reached from the initial state.

(1)  $ \Rightarrow $ (3). In this part, we show how to construct NFAs from regular expressions. Note that regular expressions have a recursive definition, so we can actually prove this part using structural induction. First, we show standard NFAs for accepting  $ \emptyset $,  $ \{\epsilon\} $, and  $ \{a\} $ (for a generic symbol  $ a $).

Next, we show how to construct NFAs for union, concatenation, and star, the three recursive operations used to define regular expressions. Note that because we’re using structural induction, it suffices to show how to perform these operations on NFAs; that is, given two NFAs  $ \mathcal{N}_1 $ and  $ \mathcal{N}_2 $, construct NFAs accepting  $ \mathcal{L}(\mathcal{N}_1) \cup \mathcal{L}(\mathcal{N}_2) $,  $ \mathcal{L}(\mathcal{N}_1) \mathcal{L}(\mathcal{N}_2) $, and  $ (\mathcal{L}(\mathcal{N}_1))^* $. We use the notation on the right to denote generic NFAs; the two accepting states on the right side of each box symbolize all accepting states of the NFAs, and their start states are  $ s_1 $ and  $ s_2 $, respectively.

First consider union. This can be accepted by the NFA shown to the right. Essentially, the idea is that starting in a new start state, we “guess” whether the word will be accepted by $\mathcal{N}_1$ or $\mathcal{N}_2$ by $\epsilon$-transitioning to either $s_1$ or $s_2$, and then see if the word is actually accepted by running the corresponding NFA.

For concatenation, we start with the first NFA  $ \mathcal{N}_1 $, and then every time we reach a final state, we “guess” that the matched string from  $ \mathcal{L}(\mathcal{N}_1) $ is complete, and  $ \epsilon $-transition to the start state of  $ \mathcal{N}_2 $.

Finally, for the Kleene star we perform a similar construction, except that the final states of  $ \mathcal{N}_1 $  $ \epsilon $-transition to  $ s_1 $ rather than  $ s_2 $. To possibly accept  $ \epsilon $, we add a new initial state that is also accepting.

(2)  $ \Rightarrow $ (1). Finally, we show how to construct regular expressions from DFAs. This is the hardest construction to prove, so our sketch here will be especially vague. The key idea is the following:

For any two states $q, r$ in a DFA, there is a regular expression that matches precisely the strings $w$ such that $\delta(q, w) = r$; i.e., the strings that induce a path from $q$ to $r$.

Let $\mathcal{D} = (Q, \Sigma, \delta, s, F)$ be a DFA with $n$ states, $Q = \{1, \ldots, n\}$. For each $i, j \in Q$, we define the sets $L_{ij} = \{w \mid \delta(i, w) = j\}$; our ultimate goal is to show that every $L_{ij}$ can be matched by a regular expression. To do this, we use a clever induction argument. For every $0 \leq k \leq n$, let

 $ L_{ij}(k) = \{w \mid \delta(i, w) = j, $ and only states  $ \leq k $ are passed between  $ i $ and  $ j\} $

Note that $L_{ij}(0)$ is the set of strings where there must be no intermediate states, i.e., $w$ is a symbol labelling a transition directly from $i$ to $j$. Also, $L_{ij}(n) = L_{ij}$: no restrictions are placed on the states that can be passed. We will show how to inductively build up regular expressions matching each of the $L_{ij}(k)$, where the induction is done on $k$. First, the base case, which we've already described intuitively:

 $$ L_{i j}(0)=\left\{\begin{aligned}{}&{{}\{a\in\Sigma\mid\delta(i,a)=j\},}&{}&{{}\mathrm{i f}i\neq j}\\ {}&{{}\{a\in\Sigma\mid\delta(i,a)=j\}\cup\{\epsilon\},}&{}&{{}\mathrm{i f}i=j}\\ \end{aligned}\right. $$

Note that when $i = j$, we need to include $\epsilon$, as this indicates the trivial act of following no transition at all. Since the $L_{ij}(0)$ are finite sets (of symbols), we can write regular expressions for them (e.g., if $L_{ij}(0) = \{a, c, f\}$, the regex would be $a + c + f$).

Finally, here is the recursive definition of the sets that will allow us to construct regular expressions: it defines  $ L_{ij}(k+1) $ in terms of some  $ L_{\ldots}(k) $, using only the operations of union, concatenation, and star:

 $$ L_{ij}(k+1)=L_{ij}(k)\cup\left(L_{i,k+1}(k)L_{k+1,k+1}(k)^{*}L_{k+1,j}(k)\right) $$

Therefore, given regular expressions for $L_{ij}(k)$, $L_{i,k+1}(k)$, $L_{k+1,k+1}(k)$, and $L_{k+1,j}(k)$, we can construct a regular expression for $L_{ij}(k+1)$.

This part was first proved by Stephen Kleene, the inventor of regular expressions and after whom the Kleene star is named.

Formally, our predicate is  $ P(k) $ : "For all states i and j, the set  $ L_{ij}(k) $ can be matched by a regex."

You can prove this fact in the Exercises.

#### Exercises

1. For each of the following regular languages over the alphabet  $ \Sigma = \{0,1\} $, design a regular expression and DFA which accepts that language. For which languages can you design an NFA that is substantially smaller than your DFA?

(a)  $ \{w \mid w \text{ contains an odd number of } 1^{\prime}s\} $

(b)  $ \{w \mid w \text{ contains exactly two } 1^{\prime}s\} $

(c)  $ \{w \mid w \text{ contains } 011\} $

(d)  $ \{w \mid w \text{ ends with } oo\} $

(e)  $ \{w \mid |w| \text{ is a multiple of } 3\} $

(f)  $ \{w \mid \text{every o in } w \text{ is eventually followed by a } 1\} $

(g)  $ \{w \mid w \text{ does not begin with } 10\} $

(h)  $ \{w \mid w \text{ is the binary representation of a multiple of three}\} $

(i)  $ \{w \mid w \text{ contains both } o\text{o and } 11 \text{ as substrings}\} $

(j)  $ \{0^n 1^m \mid m, n \in \mathbb{N}, m + n \text{ is even}\} $

(k)  $ \{w \mid w \text{ contains a substring of length at most } 5 \text{ that has at least three } 1's\} $

(1)  $ \{w \mid w \text{ has an even number of zeroes, or exactly } 2 \text{ ones}\} $

2. Let  $ L = \{w \in \{0,1\}^* \mid \text{the third character of } w \text{ is a } 1\} $. Prove that every DFA accepting  $ L $ has at least 5 states.

3. Let  $ L = \{w \in \{0,1\}^* \mid \text{the third last character of } w \text{ is a } 1\} $. Prove that every DFA accepting  $ L $ has at least 8 states. Hint: Consider the 8 binary strings of length 3.

4. Prove by induction that every finite language can be represented by a regular expression. (This shows that all finite languages are regular.)

5. Prove that the following languages are not regular.

(a)  $ \{a^{n^2} \mid n \in \mathbb{N}\} $

(b)  $ \{xx \mid x \in \{0,1\}^{*}\} $

For a bonus, what is the smallest DFA you can find that accepts L? It will have at least 8 states!

(c)  $ \{w \in \{a, b\}^* \mid w \text{ has more } a \text{'s than } b \text{'s}\} $

(d)  $ \{w \in \{0,1\}^* \mid w \text{ has two blocks of } o\text{'s with the same length}\} $

(e)  $ \{a^n b^m c^{n-m} \mid n \geq m \geq 0\} $

6. Recall that the complement of a language $L \subseteq \Sigma^*$ is the set $\overline{L} = \{w \in \Sigma^* \mid w \notin L\}$.

(a) Given a DFA $\mathcal{D} = (Q, \Sigma, \delta, s, F)$ that accepts a language $L$, describe how you can construct a DFA that accepts $\overline{L}$.

(b) Let $L$ be a language over an alphabet $\Sigma$. Prove that if $L$ is not regular, then the complement of $L$ is not regular.

A block is a maximal substring containing the same character; for example, the string 00111000001 has four blocks: 00, 111, 00000, and 1.

7. A regular expression  $ r $ is star-free if it doesn't contain any star operations. Prove that for every star-free regex  $ r, \mathcal{L}(r) $ is finite.

8. The suffix operator Suff takes as input a regular language, and outputs all possible suffixes of strings in the language. For example, if  $ L = \{aa, baab\} $ then

 $$ {S u f f}(L)=\{\epsilon,a,a a,b,a b,a a b,b a a b\}. $$

Prove that if $L$ is a regular language, then so is $Suff(L)$. (Hint: recall the definition of regular languages, and use structural induction!)

9. The prefix operator Pre takes as input a regular language, and outputs all possible prefixes of strings in the language. For example, if  $ L = \{aa, baab\} $ then

 $$ Pre(L)=\{\epsilon,a,aa,b,ba,baa,baab\}. $$

Prove that if $L$ is a regular language, then so is $\operatorname{Pre}(L)$. (Hint: recall the definition of regular languages, and use structural induction!)
