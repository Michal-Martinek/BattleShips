# BattleShips

## About
BattleShips is my first attempt to make an online game. It is a copy of the pen and pencil game called BattleShips, in Czech known as 'Lodě'. 
Currently it's work in progress.

## Requirements
You need python version 3.9 and pygame installed. 
For running the game you will need to be on the same local network as the server is, but internet access is not needed.
You can also have the server on a different network, but I haven't tested it yet.

## Running
You need to start exactly one server instance and then you can start as many clients as you wish.
```cmd
ServerMain.py
BattleShips.py
BattleShips.py
BattleShips.py
```

## Controls
You can change size of the ship you are placing with mouse wheel and it's rotation with the R key.

To unequip the ship in your hand press Q. With your hand empty you can click on a ship to pick it up or turn the mouse wheel to pick a ship from your inventory.

If you have placed all the ships you will be considered waiting for the opponent. You can toggle the waiting mode on and off by pressing G. Note if the opponent is waiting for you the game will start as soon as you place your last ship.
