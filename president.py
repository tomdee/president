#!/usr/bin/env python
# This is a very simple Python 2.7 implementation of the Information Set Monte Carlo Tree Search algorithm.
# The function ismcts(rootstate, itermax, verbose = False) is towards the bottom of the code.
# It aims to have the clearest and simplest possible code, and for the sake of clarity, the code
# is orders of magnitude less efficient than it could be made, particularly by using a 
# state.GetRandomMove() or state.DoRandomRollout() function.
# 
# An example GameState classes for Knockout Whist is included to give some idea of how you
# can write your own GameState to use ismcts in your hidden information game.
# 
# Written by Peter Cowling, Edward Powley, Daniel Whitehouse (University of York, UK) September 2012 - August 2013.
# 
# Licence is granted to freely use and distribute for any sensible/legal purpose so long as this comment
# remains in any distributed code.
# 
# For more information about Monte Carlo Tree Search check out our web site at www.mcts.ai
# Also read the article accompanying this code at ***URL HERE***

from math import *
import random
from copy import deepcopy


class GameState:
    """ A state of the game, i.e. the game board. These are the only functions which are
        absolutely necessary to implement ismcts in any imperfect information game,
        although they could be enhanced and made quicker, for example by using a 
        GetRandomMove() function to generate a random move during rollout.
        By convention the players are numbered 1, 2, ..., self.number_of_players.
    """

    def __init__(self):
        self.number_of_players = 2
        self.player_to_move = 1

    def get_next_player(self, p):
        """ Return the player to the left of the specified player
        """
        return (p % self.number_of_players) + 1

    def clone(self):
        """ Create a deep clone of this game state.
        """
        st = GameState()
        st.player_to_move = self.player_to_move
        return st

    def clone_and_randomize(self, observer):
        """ Create a deep clone of this game state, randomizing any information not visible to the specified observer player.
        """
        return self.clone()

    def do_move(self, move):
        """ update a state by carrying out the given move.
            Must update player_to_move.
        """
        self.player_to_move = self.get_next_player(self.player_to_move)

    def get_moves(self):
        """ Get all possible moves from this state.
        """
        pass

    def get_result(self, player):
        """ Get the game result from the viewpoint of player. 
        """
        pass

    def __repr__(self):
        """ Don't need this - but good style.
        """
        pass


class Card:
    """ A playing card, with rank and suit.
        rank must be an integer between 2 and 14 inclusive (Jack=11, Queen=12, King=13, Ace=14)
        suit must be a string of length 1, one of 'C' (Clubs), 'D' (Diamonds), 'H' (Hearts) or 'S' (Spades)
    """

    def __init__(self, rank, suit):
        if rank not in range(2, 14 + 1):
            raise Exception("Invalid rank")
        if suit not in ['C', 'D', 'H', 'S']:
            raise Exception("Invalid suit")
        self.rank = rank
        self.suit = suit

    def __repr__(self):
        return "??23456789TJQKA"[self.rank] + self.suit

    def __eq__(self, other):
        return self.rank == other.rank and self.suit == other.suit

    def __ne__(self, other):
        return self.rank != other.rank or self.suit != other.suit


class KnockoutWhistState(GameState):
    """ A state of the game Knockout Whist.
        See http://www.pagat.com/whist/kowhist.html for a full description of the rules.
        For simplicity of implementation, this version of the game does not include the "dog's life" rule
        and the trump suit for each round is picked randomly rather than being chosen by one of the players.
    """

    def __init__(self, n):
        """ Initialise the game state. n is the number of players (from 2 to 7).
            """
        GameState.__init__(self)
        self.number_of_players = n
        self.player_to_move = 1
        self.tricks_in_round = 7
        self.player_hands = {p: [] for p in xrange(1, self.number_of_players + 1)}
        self.discards = []
        self.current_trick = []
        self.trump_suit = None
        self.tricks_taken = {}
        self.knocked_out = {p: False for p in
                           xrange(1, self.number_of_players + 1)}
        self._deal()

    def clone(self):
        """ Create a deep clone of this game state.
        """
        st = KnockoutWhistState(self.number_of_players)
        st.player_to_move = self.player_to_move
        st.tricks_in_round = self.tricks_in_round
        st.player_hands = deepcopy(self.player_hands)
        st.discards = deepcopy(self.discards)
        st.current_trick = deepcopy(self.current_trick)
        st.trump_suit = self.trump_suit
        st.tricks_taken = deepcopy(self.tricks_taken)
        st.knocked_out = deepcopy(self.knocked_out)
        return st

    def clone_and_randomize(self, observer):
        """ Create a deep clone of this game state, randomizing any information
        not visible to the specified observer player.
        """
        st = self.clone()

        # The observer can see his own hand and the cards in the current trick,
        # and can remember the cards played in previous tricks
        seen_cards = st.player_hands[observer] + st.discards + \
                     [card for (player, card) in st.current_trick]

        # The observer can't see the rest of the deck
        unseen_cards = [card for card in st._get_card_deck()
                        if card not in seen_cards]

        # _deal the unseen cards to the other players
        random.shuffle(unseen_cards)
        for p in xrange(1, st.number_of_players + 1):
            if p != observer:
                # _deal cards to player p
                # Store the size of player p's hand
                num_cards = len(self.player_hands[p])
                # Give player p the first num_cards unseen cards
                st.player_hands[p] = unseen_cards[:num_cards]
                # Remove those cards from unseen_cards
                unseen_cards = unseen_cards[num_cards:]

        return st

    @staticmethod
    def _get_card_deck():
        """ Construct a standard deck of 52 cards.
        """
        return [Card(rank, suit) for rank in xrange(2, 14 + 1) for suit in
                ['C', 'D', 'H', 'S']]

    def _deal(self):
        """ Reset the game state for the beginning of a new round, and _deal the cards.
        """
        self.discards = []
        self.current_trick = []
        self.tricks_taken = {p: 0 for p in xrange(1, self.number_of_players + 1)}

        # Construct a deck, shuffle it, and _deal it to the players
        deck = self._get_card_deck()
        random.shuffle(deck)
        for p in xrange(1, self.number_of_players + 1):
            self.player_hands[p] = deck[:self.tricks_in_round]
            deck = deck[self.tricks_in_round:]

        # Choose the trump suit for this round
        self.trump_suit = random.choice(['C', 'D', 'H', 'S'])

    def get_next_player(self, p):
        """ Return the player to the left of the specified player, skipping players who have been knocked out
        """
        next_player = (p % self.number_of_players) + 1
        # Skip any knocked-out players
        while next_player != p and self.knocked_out[next_player]:
            next_player = (next_player % self.number_of_players) + 1
        return next_player

    def do_move(self, move):
        """ update a state by carrying out the given move.
            Must update player_to_move.
        """
        # Store the played card in the current trick
        self.current_trick.append((self.player_to_move, move))

        # Remove the card from the player's hand
        self.player_hands[self.player_to_move].remove(move)

        # Find the next player
        self.player_to_move = self.get_next_player(self.player_to_move)

        # If the next player has already played in this trick, then the trick is over
        if any(True for (player, card) in self.current_trick if
               player == self.player_to_move):
            # Sort the plays in the trick: those that followed suit (in ascending rank order), then any trump plays (in ascending rank order)
            (leader, lead_card) = self.current_trick[0]
            suited_plays = [(player, card.rank) for (player, card) in
                           self.current_trick if card.suit == lead_card.suit]
            trump_plays = [(player, card.rank) for (player, card) in
                          self.current_trick if card.suit == self.trump_suit]
            sorted_plays = sorted(suited_plays,
                                 key=lambda (aplayer, rank): rank) + sorted(
                trump_plays, key=lambda (aplayer, rank): rank)
            # The winning play is the last element in sorted_plays
            trick_winner = sorted_plays[-1][0]

            # update the game state
            self.tricks_taken[trick_winner] += 1
            self.discards += [card for (player, card) in self.current_trick]
            self.current_trick = []
            self.player_to_move = trick_winner

            # If the next player's hand is empty, this round is over
            if not self.player_hands[self.player_to_move]:
                self.tricks_in_round -= 1
                self.knocked_out = {
                p: (self.knocked_out[p] or self.tricks_taken[p] == 0) for p in
                xrange(1, self.number_of_players + 1)}
                # If all but one players are now knocked out, the game is over
                if len([x for x in self.knocked_out.itervalues() if
                        x == False]) <= 1:
                    self.tricks_in_round = 0

                self._deal()

    def get_moves(self):
        """ Get all possible moves from this state.
        """
        hand = self.player_hands[self.player_to_move]
        if not self.current_trick:
            # May lead a trick with any card
            return hand
        else:
            (leader, lead_card) = self.current_trick[0]
            # Must follow suit if it is possible to do so
            cards_in_suit = [card for card in hand if card.suit == lead_card.suit]
            if cards_in_suit:
                return cards_in_suit
            else:
                # Can't follow suit, so can play any card
                return hand

    def get_result(self, player):
        """ Get the game result from the viewpoint of player. 
        """
        return 0 if (self.knocked_out[player]) else 1

    def __repr__(self):
        """ Return a human-readable representation of the state
        """
        result = "Round %i" % self.tricks_in_round
        result += " | P%i: " % self.player_to_move
        result += ",".join(
            str(card) for card in self.player_hands[self.player_to_move])
        result += " | Tricks: %i" % self.tricks_taken[self.player_to_move]
        result += " | Trump: %s" % self.trump_suit
        result += " | Trick: ["
        result += ",".join(
            ("%i:%s" % (player, card)) for (player, card) in self.current_trick)
        result += "]"
        return result


class Node:
    """ A node in the game tree. Note wins is always from the viewpoint of player_just_moved.
    """

    def __init__(self, move=None, parent=None, player_just_moved=None):
        # the move that got us to this node - "None" for the root node
        self.move = move
        # "None" for the root node
        self.parent_node = parent
        self.child_nodes = []
        self.wins = 0
        self.visits = 0
        self.avails = 1
        # the only part of the state that the Node needs later
        self.player_just_moved = player_just_moved

    def get_untried_moves(self, legal_moves):
        """ Return the elements of legal_moves for which this node does not have children.
        """

        # Find all moves for which this node *does* have children
        tried_moves = [child.move for child in self.child_nodes]

        # Return all moves that are legal but have not been tried yet
        return [move for move in legal_moves if move not in tried_moves]

    def ucb_select_child(self, legal_moves, exploration=0.7):
        """ Use the UCB1 formula to select a child node, filtered by the given list of legal moves.
            exploration is a constant balancing between exploitation and exploration, with default value 0.7 (approximately sqrt(2) / 2)
        """

        # Filter the list of children by the list of legal moves
        legal_children = [child for child in self.child_nodes if
                          child.move in legal_moves]

        # Get the child with the highest UCB score
        s = max(legal_children, key=lambda c: float(c.wins) / float(
            c.visits) + exploration * sqrt(log(c.avails) / float(c.visits)))

        # update availability counts -- it is easier to do this now than during backpropagation
        for child in legal_children:
            child.avails += 1

        # Return the child selected above
        return s

    def add_child(self, m, p):
        """ Add a new child node for the move m.
            Return the added child node
        """
        n = Node(move=m, parent=self, player_just_moved=p)
        self.child_nodes.append(n)
        return n

    def update(self, terminal_state):
        """ update this node - increment the visit count by one, and increase the win count by the result of terminal_state for self.player_just_moved.
        """
        self.visits += 1
        if self.player_just_moved is not None:
            self.wins += terminal_state.get_result(self.player_just_moved)

    def __repr__(self):
        return "[M:%s W/V/A: %4i/%4i/%4i]" % (
        self.move, self.wins, self.visits, self.avails)

    def tree_to_string(self, indent):
        """ Represent the tree as a string, for debugging purposes.
        """
        s = self.indent_string(indent) + str(self)
        for c in self.child_nodes:
            s += c.tree_to_string(indent + 1)
        return s

    @staticmethod
    def indent_string(indent):
        s = "\n"
        for i in range(1, indent + 1):
            s += "| "
        return s

    def children_to_string(self):
        s = ""
        for c in self.child_nodes:
            s += str(c) + "\n"
        return s


def ismcts(rootstate, itermax, verbose=False):
    """ Conduct an ismcts search for itermax iterations starting from rootstate.
        Return the best move from the rootstate.
    """

    rootnode = Node()

    for i in range(itermax):
        node = rootnode

        # Determinize
        state = rootstate.clone_and_randomize(rootstate.player_to_move)

        # Select
        while state.get_moves() != [] and node.get_untried_moves(
                state.get_moves()) == []:  # node is fully expanded and non-terminal
            node = node.ucb_select_child(state.get_moves())
            state.do_move(node.move)

        # Expand
        untried_moves = node.get_untried_moves(state.get_moves())
        if untried_moves:  # if we can expand (i.e. state/node is non-terminal)
            m = random.choice(untried_moves)
            player = state.player_to_move
            state.do_move(m)
            node = node.add_child(m, player)  # add child and descend tree

        # Simulate
        while state.get_moves():  # while state is non-terminal
            state.do_move(random.choice(state.get_moves()))

        # Backpropagate
        while node:  # backpropagate from the expanded node and work back to the root node
            node.update(state)
            node = node.parent_node

    # Output some information about the tree - can be omitted
    if verbose:
        print rootnode.tree_to_string(0)
    else:
        print rootnode.children_to_string()

    return max(rootnode.child_nodes, key=lambda
        c: c.visits).move  # return the move that was most visited


def play_game():
    """ Play a sample game between two ismcts players.
    """
    state = KnockoutWhistState(4)

    while state.get_moves():
        print str(state)
        # Use different numbers of iterations (simulations, tree nodes) for different players
        if state.player_to_move == 1:
            m = ismcts(rootstate=state, itermax=1000, verbose=False)
        else:
            m = ismcts(rootstate=state, itermax=100, verbose=False)
        print "Best Move: " + str(m) + "\n"
        state.do_move(m)

    someone_won = False
    for p in xrange(1, state.number_of_players + 1):
        if state.get_result(p) > 0:
            print "Player " + str(p) + " wins!"
            someone_won = True
    if not someone_won:
        print "Nobody wins!"


if __name__ == "__main__":
    play_game()
