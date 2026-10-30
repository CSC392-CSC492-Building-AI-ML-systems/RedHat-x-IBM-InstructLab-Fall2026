# Induction

Source: David Liu, *Introduction to the Theory of Computation: Lecture Notes and Exercises for CSC236*, with UTM edits by Daniel Zingaro.

What is the sum of the numbers from 0 to $n$? This is a well-known identity you've probably seen before:

 $$ \sum_{i=0}^{n}i=\frac{n(n+1)}{2}. $$

A “proof” of this is attributed to Gauss:

 $$ \begin{aligned}1+2+3+\cdots+n-1+n&=(1+n)+(2+n-1)+(3+n-2)+\cdots\\&=(n+1)+(n+1)+(n+1)+\cdots\\&=\frac{n}{2}(n+1)\qquad\quad(since~there~are~\frac{n}{2}~pairs)\end{aligned} $$

This isn’t exactly a formal proof – what if $n$ is odd? – and although it could be made into one, this proof is based on a mathematical “trick” that doesn’t work for, say, $\sum_{i=0}^{n} i^2$. And while mathematical tricks are often useful, they’re hard to come up with in the first place! Induction gives us a different way to tackle this problem that is astonishingly straightforward.

A predicate is a parametrized logical statement. Another way to view a predicate is as a function that takes in one or more arguments, and outputs either True or False. Some examples of predicates are:

EV(n): n is even

 $$ GR(x,y):x>y $$

FROSH(a) : a is a first-year university student

Every predicate has a domain, the set of its possible input values. For example, the above predicates could have domains $\mathbb{N}$, $\mathbb{R}$, and “the set of all UofT students,” respectively. Predicates give us a precise way of formulating English problems; the predicate that is relevant to our example is

 $$ P(n):\sum_{i=0}^{n}i=\frac{n(n+1)}{2}. $$

We ignore the o in the summation, since this doesn't change the sum.

We will always use the convention that  $ 0 \in \mathbb{N} $ unless otherwise specified.

You might be thinking right now: “Okay, now we’re going to prove that  $ P(n) $ is true.” But this is wrong, because we haven’t yet defined  $ n! $. So in fact we want to prove that  $ P(n) $ is true for all natural numbers  $ n $, or written symbolically,  $ \forall n \in \mathbb{N}, P(n) $. Here is how a formal proof might go if we were not using mathematical induction:

 $$  Proof~of~\forall n\in\mathbb{N},\sum_{i=0}^{n}i=\frac{n(n+1)}{2} $$

Let  $ n \in \mathbb{N} $.

Want to prove that $P(n)$ is true.
Case 1: Assume $n$ is even.
# Gauss' trick
:
Then $P(n)$ is true.
Case 2: Assume $n$ is odd.
# Gauss' trick, with a twist?
:
Then $P(n)$ is true.
Then in all cases, $P(n)$ is true.

Then  $ \forall n \in \mathbb{N}, P(n) $.

Instead, we're going to see how induction gives us a different, easier way of proving the same thing.

#### The Induction Idea

Suppose we want to create a viral Youtube video featuring “The World’s Longest Domino Chain!!! (like plz)”.

Of course, a static image like the one featured on the right is no good for video; instead, once we have set it up we plan on recording all of the dominoes falling in one continuous, epic take. It took a lot of effort to set up the chain, so we would like to make sure that it will work; that is, that once we tip over the first domino, all the rest will fall. Of course, with dominoes the idea is rather straightforward, since we have arranged the dominoes precisely enough that any one falling will trigger the next one to fall. We can express this thinking a bit more formally:

(1) The first domino will fall (when we push it).

A common mistake: defining the predicate to be something like $P(n): \frac{n(n+1)}{2}$. Such an expression is wrong and misleading because it isn't a True/False value, and so fails to capture precisely what we want to prove.

(2) For each domino, if it falls, then the next one in the chain will fall (because each domino is close enough to the next one).

From these two thoughts, we can conclude that

(3) Every domino in the chain will fall.

We can apply the same reasoning to the set of natural numbers. Instead of “every domino in the chain will fall,” suppose we want to prove that “for all  $ n \in \mathbb{N} $,  $ P(n) $ is true”, where  $ P(n) $ is some predicate. The analogues of the above statements in the context of natural numbers are

(1)  $ P(0) $ is true (o is the “first” natural number)

(2)  $ \forall k \in \mathbb{N}, P(k) \Rightarrow P(k+1) $

(3)  $ \forall n \in \mathbb{N}, P(n) $ is true

The “is true” is redundant, but we will often include these words for clarity.

Putting these together yields the Principle of Simple Induction (also known as Mathematical Induction):

 $$ (P(0)\land\forall k\in\mathbb{N},P(k)\Rightarrow P(k+1))\Rightarrow\forall n\in\mathbb{N},P(n) $$

A different, slightly more mathematical intuition for what induction says is that “ $ P(0) $ is true, and  $ P(1) $ is true because  $ P(0) $ is true, and  $ P(2) $ is true because  $ P(1) $ is true, and  $ P(3) $ is true because… $”. However, it turns out that a more rigorous proof of simple induction doesn’t exist from the basic arithmetic properties of the natural numbers alone. Therefore mathematicians accept the principle of induction as an axiom, a statement as fundamentally true as  $ 1 + 1 = 2 $.

simple/mathematical induction

This gives us a new way of proving a statement is true for all natural numbers: instead of proving $P(n)$ for an arbitrary $n$, just prove $P(0)$, and then prove the link $P(k) \Rightarrow P(k+1)$ for an arbitrary $k$. The former step is called the base case, while the latter is called the induction step. We'll see exactly how such a proof goes by illustrating it with the opening example.

Example. Prove that for every natural number $n$, $\sum_{i=0}^{n} i = \frac{n(n+1)}{2}$.

Proof. First, we define the predicate associated with this question. This lets us determine exactly what it is we're going to use in the induction proof.

Step 1 (Define the Predicate)

 $$ P(n):\sum_{i=0}^{n}i=\frac{n(n+1)}{2} $$

It's easy to miss this step, but without it, often you'll have trouble deciding precisely what to write in your proofs.

It certainly makes sense intuitively, and turns out to be equivalent to another fundamental math fact called the Well-Ordering Principle.

The first few induction examples in this chapter have a great deal of structure; this is only to help you learn the necessary ingredients of induction proofs. We will not be marking for a particular structure in this course, but you will probably find it helpful to use our keywords to organize your proofs.

Step 2 (Base Case): $n = 0$. We would like to prove that $P(0)$ is true. Recall the meaning of $P$:

 $$ \begin{array}{r l}{P(0):}&{{}\displaystyle\sum_{i=0}^{0}i=\frac{0(0+1)}{2}.}\end{array} $$

This statement is trivially true, because both sides of the equation are equal to 0.

Step 3 (Induction Step): the goal is to prove that  $ \forall k \in \mathbb{N}, P(k) \Rightarrow P(k+1) $. Let  $ k \in \mathbb{N} $ be some arbitrary natural number, and assume  $ P(k) $ is true. This antecedent assumption has a special name: the Induction Hypothesis. Explicitly, we assume that

 $$ \sum_{i=0}^{k}i=\frac{k(k+1)}{2}. $$

Now, we want to prove that $P(k+1)$ is true, i.e., that $\sum_{i=0}^{k+1} i = \frac{(k+1)(k+2)}{2}$.

This can be done with a simple calculation:

 $$ \begin{aligned}\sum_{i=0}^{k+1}i&=\left(\sum_{i=0}^{k}i\right)+(k+1)\\&=\frac{k(k+1)}{2}+(k+1)\\&=(k+1)\left(\frac{k}{2}+1\right)\\&=\frac{(k+1)(k+2)}{2}\end{aligned} $$

(By Induction Hypothesis)

Therefore  $ P(k+1) $ holds. This completes the proof of the induction step:  $ \forall k \in \mathbb{N}, P(k) \Rightarrow P(k+1) $.

Finally, by the Principle of Simple Induction, we can conclude that  $ \forall n \in \mathbb{N}, P(n) $.

In our next example, we look at a geometric problem – notice how our proof will use no algebra at all, but instead constructs an argument from English statements and diagrams. This example is also interesting because it shows how to apply simple induction starting at a number other than 0.

Example. A triomino is a three-square L-shaped figure. To the right, we show a 4-by-4 chessboard with one corner missing that has been tiled with triominoes.

Prove that for all  $ n \geq 1 $, any  $ 2^n $-by- $ 2^n $ chessboard with one corner missing can be tiled with triminoes.

For induction proofs, the base case usually a very straightforward proof. In fact, if you find yourself stuck on the base case, then it is likely that you've misunderstood the question and/or are trying to prove the wrong predicate.

We break up the sum by removing the last element.

The one structural requirement we do have for this course is that you must always state exactly where you use the induction hypothesis. We expect to see the words "by the induction hypothesis" at least once in each of your proofs.

Proof. Predicate: $P(n)$: Any $2^n$-by$-2^n$ chessboard with one corner missing can be tiled with triominoes.

Base Case: This is slightly different, because we only want to prove the claim for $n \geq 1$ (and ignore $n = 0$). Therefore our base case is $n = 1$, i.e., this is the “start” of our induction chain. When $n = 1$, we consider a 2-by-2 chessboard with one corner missing. But such a chessboard is exactly the same shape as a triomino, so of course it can be tiled by triominoes!

Induction Step: Let  $ k \geq 1 $ and suppose that  $ P(k) $ holds; that is, that every  $ 2^k $-by- $ 2^k $ chessboard with one corner missing can be tiled by triominoes. (This is the Induction Hypothesis.) The goal is to show that any  $ 2^{k+1} $-by- $ 2^{k+1} $ chessboard with one corner missing can be tiled by triominoes.

Consider an arbitrary  $ 2^{k+1} $-by- $ 2^{k+1} $ chessboard with one corner missing. Divide it into quarters, each quarter a  $ 2^k $-by- $ 2^k $ chessboard.

Exactly one of these has one corner missing; by the Induction Hypothesis, this quarter can be tiled by triominoes. Next, place a single triomino in the middle that covers one corner in each of the three remaining quarters.

Each of these quarters now has one corner covered, and by the I.H. again, they can each be tiled by triominoes. This completes the tiling of the  $ 2^{k+1} $-by- $ 2^{k+1} $ chessboard.

Before moving on, here is some intuition behind what we did in the previous two examples. Given a problem of a  $ 2^n $-by- $ 2^n $ chessboard, we repeatedly broke it up into smaller and smaller parts, until we reached the 2-by-2 size, which we could tile using just a single tri-omino. This idea of breaking down the problem into smaller ones “again and again” was a clear sign that a formal proof by induction was the way to go. Be on the lookout for phrases like “repeat over and over” in your own thinking to signal that you should be using induction. In the opening example, we used an even more specific approach: in the induction step, we took the sum of size  $ k + 1 $ and reduced it to a sum of size  $ k $, and evaluated that using the induction hypothesis. The cornerstone of simple induction is this link between problem instances of size  $ k $ and size  $ k + 1 $, and this ability to break down a problem into something exactly one size smaller.

Example. Consider the sequence of natural numbers satisfying the following properties:  $ a_0 = 1 $, and for all  $ n \geq 1 $,  $ a_n = 2a_{n-1} + 1 $. Prove that for all  $ n \in \mathbb{N} $,  $ a_n = 2^{n+1} - 1 $.

Again, a rather trivial base case. Keep in mind that even though it was simple, the proof would have been incomplete without it!

Note that in this proof, we used the induction hypothesis twice! (Or technically, 4 times, one for each  $ 2^k $-by- $ 2^k $ quarter.)

In your programming, this is the same sign that points to using recursive solutions as the easiest approach.

We will see in the next chapter one way of discovering this expression for  $ a_{n} $.

Proof. The predicate we will prove is

 $$ P(n):a_{n}=2^{n+1}-1. $$

The base case is n = 0. By the definition of the sequence,  $ a_0 = 1 $, and  $ 2^{0+1} - 1 = 2 - 1 = 1 $, so  $ P(0) $ holds.

For the induction step, let  $ k \in \mathbb{N} $ and suppose  $ a_k = 2^{k+1} - 1 $. Our goal is to prove that  $ P(k+1) $ holds. By the recursive property of the sequence,

 $$ \begin{aligned}a_{k+1}&=2a_{k}+1\\&=2(2^{k+1}-1)+1\\&=2^{k+2}-2+1\\&=2^{k+2}-1\end{aligned} $$

### When Simple Induction Isn't Enough

By this point, you have done several examples using simple induction. Recall that the intuition behind this proof technique is to reduce problems of size  $ k+1 $ to problems of size k (where “size” might mean the value of a number, or the size of a set, or the length of a string, etc.). However, for many problems there is no natural way to reduce problem sizes just by 1. Consider, for example, the following problem:

Prove that every natural number greater than 1 has a prime factorization, i.e., can be written as a product of primes.

How would you go about proving the induction step, using the method we've used so far? That is, how would you prove  $ P(k) \Rightarrow P(k+1) $? This is a very hard question to answer, because even the prime factorizations of consecutive numbers can be completely different!

But if I asked you to solve this question by “breaking the problem down,” you would come up with the idea that if  $ k+1 $ is not prime, then we can write  $ k+1 = a \cdot b $, where  $ a, b < k+1 $, and we can “do this recursively” until we’re left with a product of primes. Since we always identify recursion with induction, this hints at a more general form of induction that we can use to prove this statement.

E.g.,  $ 210 = 2 \cdot 3 \cdot 5 \cdot 7 $, but 211 is prime.

Every prime can be written as a product of just one number: itself!

#### Complete Induction

Recall the intuitive “chain of reasoning” that we do with simple induction: first we prove $P(0)$, and then use $P(0)$ to prove $P(1)$, then use $P(1)$ to prove $P(2)$, etc. So when we get to $k+1$, we try to prove $P(k+1)$ using $P(k)$, but we have already gone through proving $P(0)$, $P(1)$, ..., and $P(k-1)$, in addition to $P(k)$! In some sense, in Simple Induction we’re throwing away all of our previous work except for $P(k)$. In Complete Induction, we keep this work and use it in our proof of the induction step. Here is the formal statement of The Principle of Complete Induction:

 $$ \left(P(0)\land\forall k,\left(P(0)\land P(1)\land\cdots\land P(k)\right)\Rightarrow P(k+1)\right)\Rightarrow\forall n,P(n) $$

The only difference between Complete and Simple Induction is in the antecedent of the inductive part: instead of assuming just $P(k)$, we now assume all of $P(0)$, $P(1)$, ..., $P(k)$. Since these are assumptions we get to make in our proofs, Complete Induction proofs are often more flexible than Simple Induction proofs — intuitively, because we have “more to work with.”

Let's illustrate this (slightly different) technique by proving the earlier claim about prime factorizations.

Example. Prove that every natural number greater than 1 has a prime factorization.

Proof. Predicate: $P(n)$: “There are primes $p_1, p_2, \ldots, p_m$ (for some $m \geq 1$) such that $n = p_1 p_2 \cdots p_m$.” We will show that $\forall n \geq 2$, $P(n)$.

Base Case: $n=2$. Since 2 is prime, we can let $p_{1}=2$ and say that $n=p_{1}$, so $P(2)$ holds.

Induction Step: Here is the only structural difference for Complete Induction proofs. We let  $ k \geq 2 $, and our induction hypothesis is now to assume that for all  $ 2 \leq i \leq k $,  $ P(i) $ holds. (That is, we're assuming  $ P(2) $,  $ P(3) $,  $ P(4) $, ...,  $ P(k) $ are all true.) The goal is still the same: prove that  $ P(k+1) $ is true.

There are two cases. In the first case, assume $k+1$ is prime. Then of course $k+1$ can be written as a product of primes, so $P(k+1)$ is true.

In the second case,  $ k + 1 $ is composite. But then by the definition of compositeness, there exist  $ a, b \in \mathbb{N} $ such that  $ k + 1 = ab $ and  $ 2 \leq a, b \leq $ complete induction

Somewhat surprisingly, everything we can prove with Complete Induction we can also prove with Simple Induction, and vice versa. So these proof techniques are equally powerful.

Azadeh Farzan gave a great analogy for the two types of induction. Simple Induction is like a person climbing stairs step by step; Complete Induction is like a robot with multiple giant legs, capable of jumping from any lower step to a higher step.

The product contains a single number,  $ k+1 $.

k; that is,  $ k + 1 $ has factors other than 1 and itself. This is the intuition from earlier. And here is the “recursive thinking”: by the induction hypothesis,  $ P(a) $ and  $ P(b) $ hold. Therefore we can write

 $$ a=q_{1}\cdots q_{l_{1}}\quad and\quad b=r_{1}\cdots r_{l_{2}}, $$

where each of the $q$'s and $r$'s is prime. But then

 $$ k+1=a b=q_{1}\cdots q_{l_{1}}r_{1}\cdots r_{l_{2}}, $$

and this is the prime factorization of  $ k+1 $. So  $ P(k+1) $ holds.

Note that we used inductive thinking to break down the problem; but unlike Simple Induction where the size of the subproblem is one less than the current problem size, we didn't know much about the sizes of the resulting problems (only that they were smaller than the original problem). Complete Induction allows us to handle this sort of structure.

Example. The Fibonacci sequence is a sequence of natural numbers defined recursively as  $ f_1 = f_2 = 1 $, and for all  $ n \geq 3 $,  $ f_n = f_{n-1} + f_{n-2} $. Prove that for all  $ n \geq 1 $,

 $$ f_{n}=\frac{(\frac{1+\sqrt{5}}{2})^{n}-(\frac{1-\sqrt{5}}{2})^{n}}{\sqrt{5}}. $$

Proof. Note that we really need complete induction here (and not just simple induction) because $f_{n}$ is defined in terms of both $f_{n-1}$ and $f_{n-2}$, and not just $f_{n-1}$ only.

The predicate we will prove is $P(n):f_n=\frac{(\frac{1+\sqrt{5}}{2})^n-(\frac{1-\sqrt{5}}{2})^n}{\sqrt{5}}$. We require two base cases: one for $n=1$, and one for $n=2$. These can be checked by simple calculations:

 $$ \begin{aligned}\frac{(\frac{1+\sqrt{5}}{2})^{1}-(\frac{1-\sqrt{5}}{2})^{1}}{\sqrt{5}}&=\frac{\frac{1+\sqrt{5}}{2}-\frac{1-\sqrt{5}}{2}}{\sqrt{5}}\\&=\frac{\sqrt{5}}{\sqrt{5}}\\&=1=f_{1}\end{aligned} $$

We can only use the induction hypothesis because a and b are at least 2 and less than  $ k+1 $.

 $$ \begin{aligned}\frac{(\frac{1+\sqrt{5}}{2})^{2}-(\frac{1-\sqrt{5}}{2})^{2}}{\sqrt{5}}&=\frac{\frac{6+2\sqrt{5}}{4}-\frac{6-2\sqrt{5}}{4}}{\sqrt{5}}\\&=\frac{\sqrt{5}}{\sqrt{5}}\\&=1=f_{2}\end{aligned} $$

For the induction step, let  $ k \geq 2 $ and assume  $ P(1), P(2), \ldots, P(k) $ hold. Consider  $ f_{k+1} $. By the recursive definition, we have

 $$ \begin{aligned}f_{k+1}&=f_{k}+f_{k-1}\\&=\frac{(\frac{1+\sqrt{5}}{2})^{k}-(\frac{1-\sqrt{5}}{2})^{k}}{\sqrt{5}}+\frac{(\frac{1+\sqrt{5}}{2})^{k-1}-(\frac{1-\sqrt{5}}{2})^{k-1}}{\sqrt{5}}\\&=\frac{(\frac{1+\sqrt{5}}{2})^{k}+(\frac{1+\sqrt{5}}{2})^{k-1}}{\sqrt{5}}-\frac{(\frac{1-\sqrt{5}}{2})^{k}+(\frac{1-\sqrt{5}}{2})^{k-1}}{\sqrt{5}}\\&=\frac{(\frac{1+\sqrt{5}}{2})^{k-1}(\frac{1+\sqrt{5}}{2}+1)}{\sqrt{5}}-\frac{(\frac{1-\sqrt{5}}{2})^{k-1}(\frac{1-\sqrt{5}}{2}+1)}{\sqrt{5}}\\&=\frac{(\frac{1+\sqrt{5}}{2})^{k-1}\cdot\frac{6+2\sqrt{5}}{4}}{\sqrt{5}}-\frac{(\frac{1-\sqrt{5}}{2})^{k-1}\cdot\frac{6-2\sqrt{5}}{4}}{\sqrt{5}}\\&=\frac{(\frac{1+\sqrt{5}}{2})^{k-1}(\frac{1+\sqrt{5}}{2})^{2}}{\sqrt{5}}-\frac{(\frac{1-\sqrt{5}}{2})^{k-1}(\frac{1-\sqrt{5}}{2})^{2}}{\sqrt{5}}\\&=\frac{(\frac{1+\sqrt{5}}{2})^{k+1}}{\sqrt{5}}-\frac{(\frac{1-\sqrt{5}}{2})^{k+1}}{\sqrt{5}}\end{aligned} $$

#### Beyond Numbers

So far, our proofs have all been centred on natural numbers. Even in situations where we have proved statements about other objects — like sets and chessboards — our proofs have always required associating these objects with natural numbers. Consider the following problem:

Prove that any non-empty binary tree has exactly one more node than edge.

We could use either simple or complete induction on this problem by associating every tree with a natural number (height and number of nodes are two of the most common). But this is not the most “natural” way of approaching this problem (though it’s perfectly valid!) because binary trees already have a lot of nice recursive structure that we should be able to use directly, without shoehorning in natural numbers. What we want is a way of proving statements about objects other than numbers. Thus we move away from  $ \mathbb{N} $ (the set of natural numbers), to more general sets (such as the set of all non-empty binary trees).

#### Recursive Definitions of Sets

You are already familiar with many descriptions of sets: $\{2, \pi, \sqrt{10}\}$, $\{x \in \mathbb{R} \mid x \geq 4\}$, and “the set of all non-empty binary trees” are all perfectly valid descriptions of sets. Unfortunately, these set descriptions don’t lend themselves very well to induction, because induction is recursion and it isn’t clear how to apply recursive thinking to any of these descriptions. However, for some objects – like binary trees – it is relatively straightforward to define them recursively. Here’s a warm-up.

Example. Suppose we want to construct a recursive definition of N. Here is one way. Define N to be the (smallest) set such that:

 $$ \bullet \quad 0\in\mathbb{N} $$

 $$ \bullet \quad \mathrm{If}~k\in\mathbb{N},~\mathrm{then}~k+1\in\mathbb{N} $$

Notice how similar this definition looks to the Principle of Simple Induction! This isn't a coincidence: induction fundamentally makes use of this recursive structure of  $ \mathbb{N} $. We'll refer to the first rule as the base of the definition, and the second as the recursive rule. In general, a recursive definition can have multiple base and recursive rules!

Example. Construct a recursive definition of “the set of all non-empty binary trees.”

Intuitively, the base rule(s) always capture the smallest or simplest elements of a set. Certainly the smallest non-empty binary tree is a single node.

What about larger trees? This is where “breaking down” problems into smaller subproblems makes the most sense. You should know from CSC148 that we really store binary trees in a recursive manner: every tree has a root node and links to the roots of the left and right subtrees (the suggestive word here is “subtree.”) One slight subtlety is that one or both of these subtrees could be empty. Here is a formal recursive definition (before you read it, try coming up with one yourself!):

- A single node is a non-empty binary tree.

• If $T_{1}, T_{2}$ are two non-empty binary trees, then the tree with a new root $r$ connected to the roots of $T_{1}$ and $T_{2}$ is a non-empty binary tree.

The “smallest” means that nothing else is in N. This is an important point to make; for example, the set of integers Z also satisfies the given properties, but includes more than N. In the recursive definitions below, we omit “smallest” but it is always implicitly there.

- If  $ T_{1} $ is a non-empty binary tree, then the tree with a new root r connected to the root of  $ T_{1} $ to the left or to the right is a non-empty binary tree.

Notice that this definition has two recursive rules, not one!

#### Structural Induction

Now, we mimic the format of our induction proofs, but with the recursive definition of non-empty binary trees rather than natural numbers. The similarity of form is why this type of proof is called structural induction. In particular, notice the identical terminology.

Example. Prove that every non-empty binary tree has one more node than edge.

Proof. As before, we need to define a predicate to nail down exactly what it is we'd like to prove. However, unlike all of the previous predicates we've seen, which have been boolean functions on natural numbers, now the domain of the predicate is the set of all non-empty binary trees.

Predicate: $P(T)$: $T$ has one more node than edge.

We will use structural induction to prove that for every non-empty binary tree  $ T, P(T) $ holds.

Base Case: Our base case is determined by the first rule. Suppose T is a single node. Then it has one node and no edges, so  $ P(T) $ holds.

Induction Step: We'll divide our proof into two parts, one for each recursive rule.

- Let  $ T_{1} $ and  $ T_{2} $ be two non-empty binary trees, and assume  $ P(T_{1}) $ and  $ P(T_{2}) $ hold. (This is the induction hypothesis.) Let T be the tree constructed by attaching a node r to the roots of  $ T_{1} $ and  $ T_{2} $. Let  $ V(G) $ and  $ E(G) $ denote the number of nodes and edges in a tree G, respectively. Then we have the equations structural induction

 $$ V(T)=V(T_{1})+V(T_{2})+1 $$

 $$ E(T)=E(T_{1})+E(T_{2})+2 $$

Note that here the domain of the predicate is NOT N, but instead the set of non-empty binary trees.

since one extra node (new root $r$) and two extra edges (from $r$ to the roots of $T_1$ and $T_2$) were added to form $T$. By the induction hypothesis, $V(T_1) = E(T_1) + 1$ and $V(T_2) = E(T_2) + 1$, and so

 $$ \begin{aligned}V(T)&=E(T_{1})+1+E(T_{2})+1+1\\&=E(T_{1})+E(T_{2})+2+1\\&=E(T)+1\end{aligned} $$

Therefore  $ P(T) $ holds.

Let  $ T_{1} $ be a non-empty binary tree, and suppose  $ P(T_{1}) $ holds. Let T be the tree formed by taking a new node r and adding an edge to the root of  $ T_{1} $. Then  $ V(T) = V(T_{1}) + 1 $ and  $ E(T) = E(T_{1}) + 1 $, and since  $ V(T_{1}) = E(T_{1}) + 1 $ (by the induction hypothesis), we have

 $$ V(T)=E(T_{1})+2=E(T)+1.\quad ■ $$

In structural induction, we identify some property that is satisfied by the simplest (base) elements of the set, and then show that the property is preserved under each of the recursive construction rules.

Here is some intuition: imagine you have a set of Lego blocks. Starting with individual Lego pieces, there are certain “rules” that you can use to combine Lego objects to build larger and larger structures, corresponding to (say) different ways of attaching Lego pieces together. This is a recursive way of describing the (infinite!) set of all possible Lego creations.

Now suppose you'd like to make a perfectly spherical object, like a soccer ball or the Death Star. Unfortunately, you look in your Lego kit and all you see are rectangular pieces! Naturally, you complain to your mother (who bought the kit for you) that you'll be unable to make a perfect sphere using the kit. But she remains unconvinced: maybe you should try doing it, she suggests, and if you're lucky you'll come up with a clever way of arranging the pieces to make a sphere. Aha! This is impossible, since you're starting with non-spherical pieces, and you (being a Lego expert) know that no matter which way you combine Lego objects together, starting with rectangular objects yields only other rectangular objects as results. So even though there are many, many different rectangular structures you could build, none of them could ever be perfect spheres.

We say that such a property is invariant under the recursive rules, meaning it isn't affected when the rules are applied. The term "invariant" will reappear throughout this course in different contexts.

### A Larger Example

Let us turn our attention to another useful example of induction: proving the equivalence of recursive and non-recursive definitions. We know from our study of Python that often problems can be solved using either recursive or iterative programs, but we've taken it for granted that these programs really can accomplish the same task. We'll look later in this course at proving things about what programs do, but for a warm-up in this section, we'll step back from programs and prove a similar type of mathematical result.

Example. Consider the following recursively defined set  $ S \subseteq \mathbb{N} * \mathbb{N} $:

 $$ \bullet \quad (0,0)\in S $$

 $$ \bullet \quad \mathrm{If}~(a,b)\in S,~\mathrm{then~both}~(a+1,b+1)\in S~\mathrm{and}~(a+3,b)\in S $$

Also, define the set  $ S' = \{(x, y) \in \mathbb{N}^* \mathbb{N} \mid x \geq y \land 3 \mid x - y\} $. Prove that these two definitions are equivalent, i.e.,  $ S = S' $.

Proof. We divide our solution into two parts. First, we show using structural induction that $S \subseteq S'$; that is, every element of $S$ satisfies the property of $S'$. Then, we prove using complete induction that $S' \subseteq S$; that is, every element of $S'$ can be constructed from the base and recursive rules of $S$.

Again, there are two recursive rules

here.

Part 1:  $ S \subseteq S' $. In this part, we show that the base case of  $ S $ is in  $ S' $, and that all elements generated using the recursive rules of  $ S $ are also in  $ S' $. For clarity, we define the predicate

The only base element of S is  $ (0,0) $. Clearly,  $ P(0,0) $ is true, as  $ 0 \geq 0 $ and  $ 3 \mid 0 $.

 $$ P(x,y):x\geq y\land3\mid x-y $$

Now for the induction step. There are two recursive rules for S. Let $(a,b)\in S$, and suppose $P(a,b)$ holds. Consider $(a+1,b+1)$. By the induction hypothesis, $a\geq b$, and so $a+1\geq b+1$. Also, $(a+1)-(b+1)=a-b$, which is divisible by 3 (again by the I.H.). So $P(a+1,b+1)$ also holds.

Here, $3 \mid x - y$ means that $x - y$ is divisible by 3.

Finally, consider $(a+3,b)$. Since $a\geq b$ (by the I.H.), $a+3\geq b$. Also, since $3\mid a-b$ (again by the I.H.), we can write $a-b=3k$. Then $(a+3)-b=3(k+1)$, so $3\mid(a+3)-b$. Therefore, $P(a+3,b)$ holds.

Although often a particular problem

lends itself more to one technique than

the other.

Part 2:  $ S' \subseteq S $. We would like to use complete induction, but we can only apply that technique to natural numbers, and not pairs of natural

numbers. So we need to associate each pair $(a,b)$ with a single natural number. We can do this by considering the sum of the pair. We define the following predicate:

 $ P(n) $ : for every  $ (x,y) \in S' $ such that  $ x + y = n $,  $ (x,y) \in S $.

It should be clear that proving  $ \forall n \in \mathbb{N}, P(n) $ is equivalent to proving that  $ S' \subseteq S $. We will prove the former using complete induction.

The base case is $n = 0$. the only element of $S'$ whose $(x,y)$ sums to $o$ is $(0,0)$, which is certainly in $S$ by the base rule of the recursive definition.

Now let $k \in \mathbb{N}$, and suppose $P(0), P(1), \ldots, P(k)$ all hold. Let $(x, y) \in S'$ such that $x + y = k + 1$. We will prove that $(x, y) \in S$. There are two cases to consider:

-  $ y > 0 $. Then since  $ x \geq y $,  $ x > 0 $. Then  $ (x - 1, y - 1) \in S' $, and  $ (x - 1) + (y - 1) = k - 1 $. By the Induction Hypothesis (in particular,  $ P(k - 1) $),  $ (x - 1, y - 1) \in S $. Then  $ (x, y) \in S $ by applying the first recursive rule in the definition of  $ S $.

• $y = 0$. Since $k + 1 > 0$, it must be the case that $x > 0$. Then since $x - y = x$, $x$ must be divisible by 3, and so $x \geq 3$. Then $(x - 3, y) \in S'$ and $(x - 3) + y = k - 2$, so by the Induction Hypothesis (in particular, $P(k - 2)$), $(x - 3, y) \in S$. Applying the second recursive rule in the definition of $S$ shows that $(x, y) \in S$.

The $>0$ checks ensure that $x-1, y-1 \in \mathbb{N}$.

Exercises

 $$ \sum_{i=0}^{n}i^{2}=\frac{n(n+1)(2n+1)}{6}. $$

1. Prove that for all  $ n \in \mathbb{N} $,

2. Let  $ a \in \mathbb{R} $,  $ a \neq 1 $. Prove that for all  $ n \in \mathbb{N} $,

 $$ \sum_{i=0}^{n}a^{i}=\frac{a^{n+1}-1}{a-1}. $$

3. Prove that for all  $ n \geq 1 $,

 $$ \sum_{k=1}^{n}\frac{1}{k(k+1)}=\frac{n}{n+1}. $$

4. Prove that  $ \forall n \in \mathbb{N} $, the units digit of  $ 4^n $ is either 1, 4, or 6.

5. Prove that  $ \forall n \in \mathbb{N}, 3 \mid 4^n - 1 $, where “ $ m \mid n $” means that  $ m $ divides  $ n $, or equivalently that  $ n $ is a multiple of  $ m $. This can be expressed algebraically as  $ \exists k \in \mathbb{N}, n = mk $.

6. Prove that for all  $ n \geq 2 $,  $ 2^n + 3^n < 4^n $.

7. Let  $ m \in \mathbb{N} $. Prove that for all  $ n \in \mathbb{N} $,  $ m \mid (m+1)^n - 1 $.

8. Prove that  $ \forall n \in \mathbb{N}, n^2 \leq 2^n + 1 $. Hint: first prove, without using induction, that  $ 2n + 1 \leq n^2 - 1 $ for  $ n \geq 3 $.

9. Find a natural number  $ k \in \mathbb{N} $ such that for all  $ n \geq k $,  $ n^3 + n < 3^n $. Then, prove this result using simple induction.

10. Prove that  $ 3^{n} < n! $ for all n > 6.

11. Prove that for every  $ n \in \mathbb{N} $, every set of size  $ n $ has exactly  $ 2^n $ subsets.

12. Find formulas for the number of even-sized subsets and odd-sized subsets of a set of size n. Prove that your formulas are correct in a single induction argument.

13. Prove, using either simple or complete induction, that any binary string begins and ends with the same character if and only if it contains an even number of occurrences of substrings from \{01,10\}.

14. A ternary tree is a tree where each node has at most 3 children. Prove that for every  $ n \geq 1 $, every non-empty ternary tree of height n has at most  $ (3^n - 1)/2 $ nodes.

15. Let  $ a \in \mathbb{R} $,  $ a \neq 1 $. Prove that for all  $ n \in \mathbb{N} $,

 $$ \sum_{i=0}^{n}i\cdot a^{i}=\frac{n\cdot a^{n+2}-(n+1)\cdot a^{n+1}+a}{(a-1)^{2}}. $$

Challenge: can you mathematically derive this formula by starting from the standard geometric identity?

16. Recall two standard trigonometric identities:

 $$ \begin{aligned}\cos(x+y)&=\cos(x)\cos(y)-\sin(x)\sin(y)\\\sin(x+y)&=\sin(x)\cos(y)+\cos(x)\sin(y)\end{aligned} $$

Also recall the definition of the imaginary number  $ i = \sqrt{-1} $. Prove, using induction, that

 $$ \left(\cos(x)+i\sin(x)\right)^{n}=\cos(nx)+i\sin(nx). $$

17. The Fibonacci sequence is an infinite sequence of natural numbers  $ f_{1}, f_{2}, \ldots $ with the following recursive definition:

 $$ f_{i}=\left\{\begin{aligned}&1,&&if i=1,2\\ &f_{i-1}+f_{i-2},&&if i>2\end{aligned}\right. $$

So your predicate should be something like "every set of size n has ... even-sized subsets and ... odd-sized subsets."

A binary string is a string containing only 0's and 1's.

(a) Prove that for all  $ n \geq 1 $,  $ \sum_{i=1}^{n} f_{i} = f_{n+2} - 1 $.

(b) Prove that for all  $ n \geq 1 $,  $ \sum_{i=1}^{n} f_{2i-1} = f_{2n} $.

(c) Prove that for all  $ n \geq 2 $,  $ f_{n}^{2} - f_{n+1}f_{n-1} = (-1)^{n-1} $.

(d) Prove that for all  $ n \geq 1 $,  $ \gcd(f_n, f_{n+1}) = 1 $.

(e) Prove that for all  $ n \geq 1 $,  $ \sum_{i=1}^{n} f_{i}^{2} = f_{n} f_{n+1} $.

18. A full binary tree is a non-empty binary tree where every node has exactly 0 or 2 children. Equivalently, every internal node (non-leaf) has exactly two children.

(a) Prove using complete induction that every full binary tree has an odd number of nodes.

(b) Prove using complete induction that every full binary tree has exactly one more leaf than internal nodes.

(c) Give a recursive definition for the set of all full binary trees.

(d) Reprove parts (a) & (b) using structural induction instead of complete induction.

19. Consider the sets of binary trees with the following property: for each node, the heights of its left and right children differ by at most 1. Prove that every binary tree with this property of height n has at least  $ (1.5)^{n} - 1 $ nodes.

20. Let  $ k > 1 $. Prove that for all  $ n \in \mathbb{N} $,  $ \left(1 - \frac{1}{k}\right)^n \geq 1 - \frac{n}{k} $.

21. Consider the following recursively defined function  $ f: \mathbb{N} \to \mathbb{N} $.

 $$ f(n)=\begin{cases}2,&if n=0\\7,&if n=1\ $ f(n-1))^{2}-f(n-2),&if n\geq2\end{cases} $$

Prove that for all  $ n \in \mathbb{N} $,  $ 3 \mid f(n) - 2 $. It will be helpful to phrase your predicate here as  $ \exists k \in \mathbb{N} $,  $ f(n) = 3k + 2 $.

22. Prove that every natural number greater than 1 can be written as the sum of prime numbers.

23. We define the set S of strings over the alphabet  $ \{[,]\} $ recursively by

•  $ \epsilon $, the empty string, is in S

• If  $ w \in S $, then so is [w]

• If  $ x, y \in S $, then so is xy

Prove that every string in $ is balanced, i.e., the number of left brackets equals the number of right brackets.

You may use the fact that for all $ a < b,

$ \gcd(a,b) = \gcd(a,b - a). $

You can choose to do induction on either the height or number of nodes in the tree. A solution with simple induction is also possible, but less generalizable.

24. The Fibonacci trees  $ T_{n} $ are a special set of binary trees defined recursively as follows.

-  $ T_{1} $ and  $ T_{2} $ are binary trees with only a single node.

• For $n > 2$, $T_n$ consists of a root node whose left subtree is $T_{n-1}$, and whose right subtree is $T_{n-2}$.

(a) Prove that for all  $ n \geq 2 $, the height of  $ T_n $ is n - 2.

(b) Prove that for all $n \geq 1$, $T_n$ has $f_n$ leaves, where $f_n$ is the $n$-th Fibonacci number.

25. Consider the following recursively defined set  $ S \subset \mathbb{N}^2 $.

•  $ 2 \in S $

• If  $ k \in S $, then  $ k^2 \in S $

• If  $ k \in S $, and  $ k \geq 2 $, then  $ \frac{k}{2} \in S $

(a) Prove that every element of $S$ is a power of $2$, i.e., can be written in the form $2^m$ for some $m \in \mathbb{N}$.

(b) Prove that every power of 2 (including  $ 2^{0} $) is in S.

26. Consider the set  $ S \subset \mathbb{N}^2 $ of ordered pairs of integers defined by the following recursive definition:

(3,2)∈S

• If  $ (x,y) \in S $, then  $ (3x - 2y, x) \in S $

Also consider the set  $ S' \subset \mathbb{N}^2 $ with the following non-recursive definition:

 $$ S^{\prime}=\{(2^{k+1}+1,2^{k}+1)\mid k\in\mathbb{N}\}. $$

Prove that $S = S^{\prime}$, or in other words, that the recursive and non-recursive definitions agree.

27. We define the set of propositional formulas  $ PF $ as follows:

• Any proposition $P$ is a propositional formula.

• If $F$ is a propositional formula, then so is $\neg F$.

- If  $ F_1 $ and  $ F_2 $ are propositional formulas, then so are  $ F_1 \land F_2 $,  $ F_1 \lor F_2 $,  $ F_1 \Rightarrow F_2 $, and  $ F_1 \Leftrightarrow F_2 $.

Prove that for all propositional formulas $F$, $F$ has a logically equivalent formula $G$ such that $G$ only has negations applied to propositions. For example, we have the equivalence

 $$ \neg(\neg(P\land Q)\Rightarrow R)\iff(\neg P\lor\neg Q)\land\neg R $$

Hint: you won't have much luck applying induction directly to the statement in the question. (Try it!) Instead, prove the stronger statement: "F and  $ \neg F $ have equivalent formulas that only have negations applied to propositions."

28. It is well-known that Facebook friendships are the most important relationships you will have in your lifetime. For a person x on Facebook, let  $ f_x $ denote the number of friends x has. Find a relationship between the total number of Facebook friendships in the world, and the sum of all of the  $ f_x $'s (over every person on Facebook). Prove your relationship using induction.

29. Consider the following 1-player game. We start with $n$ pebbles in a pile, where $n \geq 1$. A valid move is the following: pick a pile with more than 1 pebble, and divide it into two smaller piles. When this happens, add to your score the product of the sizes of the two new piles. Continue making moves until no more can be made, i.e., there are $n$ piles each containing a single pebble.

Prove using complete induction that no matter how the player makes her moves, she will always score  $ \frac{n(n-1)}{2} $ points when playing this game with n pebbles.

30. A certain summer game is played with $n$ people, each carrying one water balloon. The players walk around randomly on a field until a buzzer sounds, at which point they stop. You may assume that when the buzzer sounds, each player has a unique closest neighbour. After stopping, each player then throws his water balloon at their closest neighbour. The winners of the game are the players who are dry after the water balloons have been thrown (assume everyone has perfect aim).

Prove that for every odd  $ n $, this game always has at least one winner.

The following problems are for the more mathematically-inclined students.

1. The Principle of Double Induction is as follows. Suppose that  $ P(x, y) $ is a predicate with domain  $ \mathbb{N}^2 $ satisfying the following properties:

(1)  $ P(0,y) $ holds for all  $ y \in \mathbb{N} $

(2) For all  $ (x,y) \in \mathbb{N}^2 $, if  $ P(x,y) $ holds, then so does  $ P(x+1,y) $.

Then we may conclude that for all  $ x, y \in \mathbb{N} $,  $ P(x, y) $.

Prove that the Principle of Double Induction is equivalent to the Principle of Simple Induction.

2. Prove that for all  $ n \geq 1 $, and positive real numbers  $ x_1, \ldots, x_n \in \mathbb{R}^+ $,

 $$ \frac{1-x_{1}}{1+x_{1}}\times\frac{1-x_{2}}{1+x_{2}}\times\cdots\times\frac{1-x_{n}}{1+x_{n}}\geq\frac{1-S}{1+S}, $$

So this game is completely determined by the starting conditions, and not at all by the player's choices. Sounds fun.

where  $ S = \sum_{i=1}^{n} x_{i} $.

3. A unit fraction is a fraction of the form  $ \frac{1}{n}, n \in \mathbb{Z}^{+} $. Prove that every rational number  $ 0 < \frac{p}{q} < 1 $ can be written as the sum of distinct unit fractions.
