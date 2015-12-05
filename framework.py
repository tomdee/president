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
from operator import attrgetter
import random

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

class Deck:
    """
    A deck of cards
    """
    def __init__(self):
        self.cards = [Card(rank, suit) for rank in xrange(2, 14 + 1) for suit in
                ['C', 'D', 'H', 'S']]

    def shuffle(self):
        random.shuffle(self.cards)


class Card(object):
    """
    A playing card, with rank and suit.
    rank must be an integer between 2 and 14 inclusive (Jack=11, Queen=12, King=13, Ace=14)
    suit must be a string of length 1, one of 'C' (Clubs), 'D' (Diamonds), 'H' (Hearts) or 'S' (Spades)
    """

    def __init__(self, rank, suit):
        # if rank not in range(2, 14 + 1):
        #     raise Exception("Invalid rank")
        # if suit not in ['C', 'D', 'H', 'S']:
        #     raise Exception("Invalid suit")
        self.rank = rank
        self.suit = suit

    def __repr__(self):
        return "??3456789TJQKA2"[self.rank] + self.suit

    def __eq__(self, other):
        return self.rank == other.rank and self.suit == other.suit

    def __ne__(self, other):
        return self.rank != other.rank or self.suit != other.suit


class Node:
    """
    A node in the game tree. Note wins is always from the viewpoint of player_just_moved.
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
        """
        Return the elements of legal_moves for which this node does not have children.
        """

        # Find all moves for which this node *does* have children
        tried_moves = [child.move for child in self.child_nodes]

        # Return all moves that are legal but have not been tried yet
        return [move for move in legal_moves if move not in tried_moves]

    def ucb_select_child(self, legal_moves, exploration=0.7):
        """
        Use the UCB1 formula to select a child node, filtered by the given list of legal moves.
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
        """
        Add a new child node for the move m.
        Return the added child node
        """
        n = Node(move=m, parent=self, player_just_moved=p)
        self.child_nodes.append(n)
        return n

    def update(self, terminal_state):
        """
        update this node - increment the visit count by one, and increase the win count by the result of terminal_state for self.player_just_moved.
        """
        self.visits += 1
        if self.player_just_moved is not None:
            self.wins += terminal_state.get_result(self.player_just_moved)

    def __repr__(self):
        return "[M:%s W/V/A: %4i/%4i/%4i]" % (
        self.move, self.wins, self.visits, self.avails)

    def tree_to_string(self, indent):
        """
        Represent the tree as a string, for debugging purposes.
        """
        s = self.indent_string(indent) + str(self)
        for c in sorted(self.child_nodes, key=attrgetter('visits', 'wins')):
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
        for c in sorted(self.child_nodes, key=attrgetter('visits', 'wins')):
            s += str(c) + "\n"
        return s


def ismcts(rootstate, itermax, verbose=False):
    """
    Conduct an ismcts search for itermax iterations starting from rootstate.
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