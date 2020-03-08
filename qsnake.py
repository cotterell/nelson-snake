#! /usr/bin/env python3
import snake
import pygame
import constant
import numpy as np
import pandas as pd
from random import randint
import bitmap
import itertools
import statistics
import datetime
from scipy.stats import describe
import json
from queue import Queue
import multiprocessing


class QGame(snake.Game):
    """
    Snake Game using Q-Learning Algorithm in place of user input.

    Inherits from snake.Game
    """

    def __init__(self, training=False, watchTraining=False):
        snake.Game.__init__(self, windowWidth=1280, noBoundry=False, assist=False, screen=watchTraining)
        self.snake = Snake(self)
        self.current_state = QTable.encodeState(self.snake, self.food)
        self.qTable = QTable(self)
        self.current_action = self.qTable.chooseAction()
        self.speedOfUpdate = 1.5
        self.pause = False
        self.training = training
        self.watchTraining = watchTraining if training else True
        if watchTraining:
            self.text.append(snake.DisplayText(self.screen, (10, 30), "Learning Rate: ", self.font, str(.1)))
            self.text.append(snake.DisplayText(self.screen, (10, 50), "Discount Factor: ", self.font, str(.9)))
            self.text.append(snake.DisplayText(self.screen, (10, 70), "Current Encoded State: ", self.font, self.current_state))
            self.text.append(snake.DisplayText(self.screen, (10, 90), "Current Action: ", self.font, self.current_action))
            self.text.append(snake.DisplayText(self.screen, (10, 110), "Current Reward: ", self.font, str(self.snake.getReward(self.current_state))))
            self.text.append(snake.DisplayText(self.screen, (10, 130), "Current Q-Table entry: ", self.font))
            self.text.append(snake.DisplayText(self.screen, (20, 150), "UP: ", self.font))
            self.text.append(snake.DisplayText(self.screen, (20, 170), "DOWN: ", self.font))
            self.text.append(snake.DisplayText(self.screen, (20, 190), "LEFT: ", self.font))
            self.text.append(snake.DisplayText(self.screen, (20, 210), "RIGHT: ", self.font))
            self.text.append(snake.DisplayText(self.screen, (20, 230), "Training: ", self.font, str(self.training)))

    def userInput(self, key):
        """
        Allow the user to speed up, slow down, or pause the game to better view
        the AI
        """
        if key == pygame.K_DOWN:
            self.speedOfUpdate += .1
        elif key == pygame.K_UP:
            self.speedOfUpdate -= .1
        elif key == pygame.K_SPACE and self.watchTraining:
            self.pause = ~self.pause
        elif key == pygame.K_s and self.pause and self.watchTraining:
            self.step()
            self.drawBoard()
        elif key == pygame.K_d: 
            if not self.watchTraining:
                pygame.display.init()
                self.watchTraining = True
                self.screen = pygame.display.set_mode((1280, 600))
                for text in self.text:
                    text.setScreen(self.screen)
                self.drawBoard()
            else:
                self.watchTraining = False
                pygame.display.quit()
                pygame.display.init()

    def step(self):
        """
        Takes a full step into the execution of the algorithm. The snake moves and the text on the screen is updated
        """
        action_to_take = self.qTable.chooseAction()
        self.snake.changeDirection(snake.Direction[action_to_take])
        self.snake.move()
        old_state = self.current_state
        self.current_state = QTable.encodeState(self.snake, self.food)
        reward = self.snake.getReward(self.current_state)
        self.qTable.updateQValue(
            old_state, self.current_state, action_to_take, reward)
        self.current_action = action_to_take
        if self.watchTraining:
            self.text[3].reset(displayString=self.current_state)
            self.text[4].reset(displayString=self.current_action)
            self.text[5].reset(displayString=str(reward))
            self.text[7].reset(displayString=str(self.qTable.getRow(self.current_state, self.snake).at["UP"]))
            self.text[8].reset(displayString=str(self.qTable.getRow(self.current_state, self.snake).at["DOWN"]))
            self.text[9].reset(displayString=str(self.qTable.getRow(self.current_state, self.snake).at["LEFT"]))
            self.text[10].reset(displayString=str(self.qTable.getRow(self.current_state, self.snake).at["RIGHT"]))

    def play(self):
        """
        Main game loop. Handles movement and updating screen
        """
        timer = 0
        while not self.done:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.done = True
                    quit()
                if event.type == pygame.KEYDOWN:
                    self.userInput(event.key)

            if self.training and not self.watchTraining:
                self.step()
                self.clock.tick()
                continue

            if self.pause:
                continue

            if timer * self.speed > self.speedOfUpdate:  # Controls the speed of the snake
                timer = 0
                self.step()

            self.drawBoard()
            timer += self.clock.tick(self.fps) / 1000



    def reset(self, learning_rate=None, discount_factor=None, assist=None,
    noBoundry=None, training=None, newQ=False):
        """
        Resets the game without resetting the Q-Table
        """
        self.snake = Snake(self)
        self.score = 0
        self.current_action = self.qTable.chooseAction()
        self.food = snake.Food(self)
        self.done = False
        self.qTable = QTable(self) if newQ else self.qTable
        if hasattr(self, "scoreText"):
            self.scoreText.reset()
        learning = learning_rate if learning_rate != None else self.qTable.learning_rate
        discount_factor = discount_factor if discount_factor != None else self.qTable.discount_factor
        assist = assist if assist != None else self.assist
        noBoundry = noBoundry if noBoundry != None else self.noBoundry
        self.watchTraining = False if training and \
        self.watchTraining else self.watchTraining
        self.training = training if training != None else self.training
        self.qTable.setLearning(learning)
        self.qTable.setDiscount(discount_factor)
        self.assist = assist
        self.noBoundry = noBoundry

class QTable(pd.DataFrame):
    """
    QTable to hold all of the data during the iterations of the game.

    Inherits from pandas.DataFrame

    Instance Methods:
    addRow()
    getRow()
    chooseAction()

    private Methods:
    __etAvailableDirections()

    Static Methods:
    findIndiciesOfOccurences()
    """

    def __init__(self, game, learning_rate=.1, discount_factor=.9, epsilon=0):
        pd.DataFrame.__init__(self, columns=constant.COLUMNS, dtype=np.float32)
        self.game=game
        self.learning_rate=learning_rate
        self.discount_factor=discount_factor
        self.epsilon = epsilon

    def setLearning(self, value):
        self.learning_rate = value

    def setDiscount(self, value):
        self.discount_factor = value

    @staticmethod
    def findIndiciesOfOccurences(row, check_value):
        """
        Finds the indexes of the given value in the given row.

        Arguments:
        row - pandas.Series
        value - value held in row.

        returns - list of indexes that hold the value, empty list if no values are found.
        """
        return [index for index, value in row.items() if value == check_value]

    def __addRow(self, index, snake_obj):
        """
        Adds a blank row to the QTable and updates the instance of self.

        Arguments:
        index - the name for the row that will be added.
        """
        columns = [direction.name for direction in snake.Direction if direction.name != snake_obj.getDirection().flips().name and direction.name != "NONE"]
        newQTable=self.append(
            pd.DataFrame(
                [[0, 0, 0]], index=[index], columns=columns))
        # Changing self doesn't work, must change self this way
        self.__dict__.update(newQTable.__dict__)

    def getRow(self, index, snake):
        """
        Returns the row of the QTable in index. If the index doesn't exist, it is created and returned.

        Arguments:
        index - the state mapping to check if it already exists. If it doesn't exist, it is added.

        return - the row of the QTable related to the state that was passed.
        """
        try:
            return self.loc[index]
        except KeyError:
            self.__addRow(index, snake)
            # Recursive call to get the location after it has been added
            return self.getRow(index, snake)

    def chooseAction(self):
        """
        Chooses the next action for the actor to take.

        Looks up the available actions and chooses the best action based on the learning_rate

        returns the action for the actor to take by the name value of the Direction enum.
        """
        if randint(0, 10) * .1 < self.epsilon:  # *.1 in order to convert the int to a decimal and 0,10 for 0, 100%
            available_directions=self.__getAvailableDirections()
            next_action=available_directions[randint(
                0, len(available_directions)-1)]
        else:
        # if True:
            possible_actions=QTable.findIndiciesOfOccurences(self.getRow(
                self.game.current_state, self.game.snake), self.getRow(self.game.current_state, self.game.snake).max())
            next_action=possible_actions[randint(0, len(possible_actions)-1)]
        return next_action

    def __getAvailableDirections(self):
        """
        Returns a list of all the available direction names.

        Filters out the current direction and the flip direction (because the snake can't go further forward or back into itself)
        """
        # Can the snake keep going forward? If this is updated every frame then the actor can definitely continue going straight.
        return [direction.name for direction in snake.Direction
                if direction != self.game.snake.getDirection()
                and direction != self.game.snake.getDirection().flip()
                and direction != snake.Direction.NONE]

    def updateQValue(self, current_state, next_state, action, reward):
        """
        Update the Qvalue for the current state using the QLearning algorithm
        Q(current) = Q(current) + learning_rate * (reward + discount * max(Q(current)) - Q(current))

        Arguments:
        current_state - the state to update
        next_state - the state the actor will be in choosing the action from the current state
        action - the action that has been chosen
        reward - The reward received for moving into the new state
        """
        currentRow=self.getRow(current_state, self.game.snake)
        nextRow=self.getRow(next_state, self.game.snake)
        value=currentRow.at[action]

        newValue=reward + self.discount_factor * nextRow.max() - value

        #print(f"nextRow.max = {nextRow.max()}, value = {value}, newValue =\
        #    {newValue}, putting_new = {value + self.learning_rate * newValue} \
        #    discount = {self.discount_factor}, reward = {reward} \
        #    learning = {self.learning_rate}")
        currentRow.at[action]=value + (self.learning_rate * newValue)

    @staticmethod
    def __mapSurrounding(snake, minimum):
        """
        Maps the surrounding of the head of the snake for use in the encodeSate() function. 
        """
        tail_placeholder = [i for i in range(0, minimum)] 
        return [(x, y, block) for x in range(snake.x - snake.width, snake.x + snake.width * 2, snake.width)
                       for y in range(snake.y - snake.width, snake.y + snake.width * 2, snake.width)
                       for (block, place) in itertools.zip_longest(snake.tail[1:], tail_placeholder)
                       if (x, y) != (snake.x, snake.y)]

    @staticmethod
    def encodeState(snake_obj, food):
        """
        Encodes a state into the following format:

        direction,quadrantOfFood,BottomRight,Right,TopRight,Bottom,Top,BottomLeft,Left,TopLeft
        
        Direction:
        00 - Up
        01 - Left
        10 - Down
        11 - Right

        Quadrant:
        00 - I
        01 - II
        10 - III
        11 - IV

        Surrounding bits: 
        1 - Obstacle
        0 - Safe

        returns the encoded string as a bitmap
        """
        # Note, in range() the stop parameter is set as x + width * 2 because the end value is not inclusive
        # Here, we are Getting the 8 blocks surrounding the head (in the order of the encoding) and for each of
        # the 8 blocks we are attaching every piece of the tail. This will give 8 * len(tail) values to compare.
        minimum_value = 1 if len(snake_obj.tail) == 0 else len(snake_obj.tail) #To fix mod by 0 error

        surrounding = QTable.__mapSurrounding(snake_obj, minimum_value)

        # 2 bits for direction, 2 bits for quadrant, one bit each for 8 square locations around snake
        encoded_map=bitmap.BitMap(12)

        # Checks each block in the surrounding and checks if it is near a wall, or near a piece of the tail
        bit_position=0
        for (index, (x, y, block)) in enumerate(surrounding):
            if index % minimum_value == 0 and index != 0:  # Don't increment immediately
                bit_position += 1
            if (x < snake_obj.game.leftBoundry or y < 0 or x == snake_obj.game.rightBoundry or y == constant.WINDOW_HEIGHT
                or (block != None and block.colliderect(snake.Block(constant.BLOCK_SIZE, x, y)))
                and not encoded_map.test(bit_position)):

                encoded_map.set(bit_position)

        QTable.__encodeFoodPosition(snake_obj, food, encoded_map)
        QTable.__encodeDirection(snake_obj, encoded_map)

        return encoded_map.tostring()[4:] #We only need 12 bits, not 16

    @staticmethod
    def __encodeFoodPosition(snake, food, bitmap):
        """
        Encodes the position of the food into the bitmap

        Arguments:
        snake - Snake object
        food - Food object
        bitmap - Bitmap of surrounding

        Helper function for encodeState()
        """
        if food.x > snake.x and food.y <= snake.y:
            pass  # 00 is for top right
        elif food.x <= snake.x and food.y < snake.y:
            bitmap.set(8)
        elif food.x < snake.x and food.y >= snake.y:
            bitmap.set(9)
        else:
            bitmap.set(8)
            bitmap.set(9)

    @staticmethod
    def __encodeDirection(snake, bitmap):
        """
        Encodes the direction of the snake into the bitmap

        Arguments:
        snake - Snake object
        bitmap - Bitmap of surrounding
        
        Helper function for encodeState()
        """
        if snake.getDirection().name == "UP":
            pass #00 for up
        elif snake.getDirection().name == "LEFT":
            bitmap.set(10)
        elif snake.getDirection().name == "DOWN":
            bitmap.set(11)
        elif snake.getDirection().name == "RIGHT":
            bitmap.set(10)
            bitmap.set(11)

class Snake(snake.Snake):
    def __init__(self, game):
        snake.Snake.__init__(self, game)
        self.last_length=0
        self.last_distance = self.distanceToFood()

    def getReward(self, state):
        """
        Returns the reward of the state

        Arguments:
        state - the state that the snke is in
        """
        new_distance = self.distanceToFood()
        if len(self.tail) > self.last_length:  # An apple was eaten
            self.last_length=len(self.tail)
            reward = 1
        elif self.hit_wall or self.hit_self:
            reward = -100
        elif new_distance < self.last_distance:
            reward = .1
        else:
            reward = -.2

        self.last_distance = new_distance

        return reward

    def die(self):
        """
        Print the QTable upon death
        """
        self.game.done = True
        # print(f"Final score = {self.game.score}")
        # print(self.game.qTable)

def experiment(replications, trials):
    """
    Train the snake over different trial counts; each trial count is replicated multiple times.

    Argument List:
    replications - Number of replications
    trials - Number of trials per replication

    returns list of scores; len(list) == replications
    """
    final_scores = []
    game = QGame(training=True, watchTraining=False)
    for replication in range(0, replications):
        game.reset(newQ=True, learning_rate=.9)
        #print(f"replication = {replication}")
        for trial in range(0, trials):
            #print(f"trial = {trial}")
            game.play()
            game.reset()
        game.play()
        final_scores += [game.score]

    return final_scores

def train(replications, trial_set, out_file_name=None):
    records = []
    out_file = None
    processes = []
    process_queue = Queue()

    formatted_input = []
    for trial in trial_set:
        formatted_input.append((replications, trial))

    with multiprocessing.Pool() as pool:
        results = pool.starmap(experiment, formatted_input)

    #for trials in trial_set:
    #    #with multiprocessing.Pool() as pool:
    #    #    print(pool.starmap(experiment, [(replications, trials)]))

    #    print(experiment(replications, trials))

        #final_scores = experiment(replications, trials)
    for final_scores, trials in zip(results, trial_set):
        record = {
            'trials': trials,
            'replications': replications,
            'final_scores': final_scores
        }
        record['final_scores'] = str(record['final_scores'])[1:-1].replace(',', '')
        records += [record]
    print(records)
    exit()
    if out_file_name:    
        with open(out_file_name, "r+") as out_file:
            first_line = out_file.readline().strip()
            count = int(first_line[first_line.find('=') + 1:])
            new_line = first_line.replace(str(count), str(count+1))
            out_file.seek(0) #Go back to beginning of file
            out_file.write(new_line)

            out_file.seek(0, 2) #Move to end of file
            out_file.write("Training: " + str(count + 1) + '\n')
            out_file.write(json.dumps(records, indent=4) + '\n')
    #else:
    for record in records:
        print(f"Trials: {trials}; Replications: {replications}")
        print(describe([int(x) for x in record['final_scores'] if x != ' ']))

def main():
    # 14 cols, 19 rows
    #train(50, [i for i in range(10, 100 + 10, 10)], "train_file.txt")
    train(50, [1, 2, 3, 4, 5, 6], "train_file.txt")
    
if __name__ == "__main__":
    main()
